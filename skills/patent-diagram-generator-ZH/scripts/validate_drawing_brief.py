#!/usr/bin/env python3
"""校验中国专利绘图合同及其来源证据绑定。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_ID = "cn-patent-drawing-brief/v2"
SCHEMA_ID_V3 = "cn-patent-drawing-brief/v3"
SUPPORTED_SCHEMA_IDS = {SCHEMA_ID, SCHEMA_ID_V3}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
COMPONENT_RE = re.compile(r"^[0-9]+$")
STEP_RE = re.compile(r"^S[0-9]+$")


def load_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("绘图合同含 BOM，必须使用 UTF-8 无 BOM")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("绘图合同顶层必须是对象")
    return value


def resolve_under(case_dir: Path, raw: str, label: str) -> Path:
    candidate = Path(raw)
    candidate = candidate.resolve() if candidate.is_absolute() else (case_dir / candidate).resolve()
    try:
        candidate.relative_to(case_dir)
    except ValueError as exc:
        raise ValueError(f"{label}必须位于案件目录内：{raw}") from exc
    return candidate


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_brief(brief_path: Path, case_dir: Path) -> dict[str, Any]:
    brief = load_json(brief_path)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def error(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    def warning(code: str, message: str) -> None:
        warnings.append({"code": code, "message": message})

    schema_id = brief.get("schema_id")
    if schema_id not in SUPPORTED_SCHEMA_IDS:
        error("BRIEF-SCHEMA", f"schema_id 必须为 {SCHEMA_ID} 或 {SCHEMA_ID_V3}")
    elif schema_id == SCHEMA_ID:
        warning("BRIEF-LEGACY", "v2 未冻结阅读层级、复杂度预算、正文图示声明和独立线路通道；新案件必须使用 v3")
    if brief.get("production_skill") != "drawio-skill":
        error("BRIEF-PRODUCER", "production_skill 必须为 drawio-skill")

    constraints = brief.get("global_constraints")
    expected_constraints = {
        "figure_number_on_canvas": False,
        "edge_labels_allowed": False,
        "annotation_nodes_may_be_edge_endpoints": False,
        "official_drawio_export_required": True,
        "visual_review_required": True,
    }
    if schema_id == SCHEMA_ID_V3:
        expected_constraints.update({
            "single_primary_question_required": True,
            "independent_route_channels_required": True,
            "final_png_visual_review_required": True,
        })
    if not isinstance(constraints, dict):
        error("BRIEF-CONSTRAINTS", "缺少 global_constraints 对象")
        constraints = {}
    for key, expected in expected_constraints.items():
        if constraints.get(key) != expected:
            error("BRIEF-CONSTRAINTS", f"{key} 必须为 {expected!r}")
    color_policy = constraints.get("color_policy")
    if not isinstance(color_policy, dict):
        error("BRIEF-COLOR", "缺少 color_policy 对象")
        color_policy = {}
    mode = color_policy.get("mode")
    if mode not in {"monochrome", "restrained_color"}:
        error("BRIEF-COLOR", "color_policy.mode 必须为 monochrome 或 restrained_color")
    if color_policy.get("grayscale_safe") is not True or color_policy.get("color_semantics_redundant") is not True:
        error("BRIEF-COLOR", "颜色必须灰度安全，且不得作为唯一语义载体")
    max_fills = color_policy.get("max_nonwhite_fills")
    if not isinstance(max_fills, int) or isinstance(max_fills, bool) or not 0 <= max_fills <= 3:
        error("BRIEF-COLOR", "max_nonwhite_fills 必须为0—3的整数")
    for field in ("allowed_fill_colors", "allowed_stroke_colors"):
        values = color_policy.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(item, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", item) for item in values):
            error("BRIEF-COLOR", f"{field} 必须是非空的 #RRGGBB 数组")
    dpi = constraints.get("minimum_png_dpi", 300)
    if not isinstance(dpi, (int, float)) or isinstance(dpi, bool) or dpi < 150:
        error("BRIEF-DPI", "minimum_png_dpi 必须不小于 150")

    source_artifacts = brief.get("source_artifacts")
    if not isinstance(source_artifacts, list):
        error("BRIEF-SOURCES", "source_artifacts 必须是数组")
        source_artifacts = []
    source_ids: set[str] = set()
    source_texts: list[str] = []
    source_text_by_id: dict[str, str] = {}
    bound_sources: list[dict[str, Any]] = []
    for index, item in enumerate(source_artifacts, start=1):
        if not isinstance(item, dict):
            error("BRIEF-SOURCES", f"第 {index} 个来源不是对象")
            continue
        artifact_id, raw_path, digest = item.get("artifact_id"), item.get("path"), item.get("sha256")
        if not isinstance(artifact_id, str) or artifact_id in source_ids:
            error("BRIEF-SOURCES", f"第 {index} 个来源 artifact_id 缺失或重复")
            continue
        source_ids.add(artifact_id)
        if not isinstance(raw_path, str) or not raw_path:
            error("BRIEF-SOURCES", f"来源 {artifact_id} 缺少 path")
            continue
        try:
            path = resolve_under(case_dir, raw_path, f"来源 {artifact_id}")
        except ValueError as exc:
            error("BRIEF-SOURCES", str(exc))
            continue
        if not path.is_file():
            error("BRIEF-SOURCE-MISSING", f"来源不存在：{raw_path}")
            continue
        actual = sha256(path)
        if not isinstance(digest, str) or not SHA_RE.fullmatch(digest) or digest != actual:
            error("BRIEF-SOURCE-STALE", f"来源 {artifact_id} 的 SHA-256 与当前文件不一致")
        try:
            source_text = path.read_text(encoding="utf-8")
            source_texts.append(source_text)
            source_text_by_id[artifact_id] = source_text
        except UnicodeDecodeError:
            warning("BRIEF-SOURCE-BINARY", f"来源 {artifact_id} 不是 UTF-8 文本，未执行 anchor 文本核对")
        bound_sources.append({"artifact_id": artifact_id, "path": str(path), "sha256": actual})
    for required in ("claims", "specification", "feature_ledger"):
        if required not in source_ids:
            error("BRIEF-SOURCES", f"缺少必需来源：{required}")
    source_corpus = "\n".join(source_texts)

    output_root_raw = brief.get("output_root")
    output_root: Path | None = None
    if not isinstance(output_root_raw, str) or not output_root_raw:
        error("BRIEF-OUTPUT", "缺少 output_root")
    else:
        try:
            output_root = resolve_under(case_dir, output_root_raw, "output_root")
        except ValueError as exc:
            error("BRIEF-OUTPUT", str(exc))

    figures = brief.get("figures")
    if not isinstance(figures, list) or not figures:
        error("BRIEF-FIGURES", "figures 必须是非空数组")
        figures = []
    numbers: list[int] = []
    stems: set[str] = set()
    figure_reports: list[dict[str, Any]] = []
    for index, figure in enumerate(figures, start=1):
        if not isinstance(figure, dict):
            error("BRIEF-FIGURE", f"第 {index} 幅图不是对象")
            continue
        number = figure.get("figure_number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            error("BRIEF-FIGURE", f"第 {index} 幅图的 figure_number 无效")
            continue
        numbers.append(number)
        stem = figure.get("file_stem")
        if not isinstance(stem, str) or not stem.strip() or stem in stems:
            error("BRIEF-FIGURE", f"图{number} file_stem 缺失或重复")
        else:
            stems.add(stem)
            if not stem.startswith(f"图{number}-"):
                warning("BRIEF-FILENAME", f"图{number} file_stem 建议以“图{number}-”开头")
        if figure.get("diagram_type") not in {
            "system_block", "method_flowchart", "interaction_sequence", "state_machine",
            "data_flow", "internal_structure", "cross_functional_flow",
            "network_topology", "data_structure"
        }:
            error("BRIEF-DIAGRAM-TYPE", f"图{number} diagram_type 不在专利适配图型中")
        expected_profile = "patent_monochrome" if mode == "monochrome" else "patent_restrained_color"
        if figure.get("style_profile") != expected_profile:
            error("BRIEF-COLOR", f"图{number} style_profile 必须为 {expected_profile}")

        layer_ids: set[str] = set()
        if schema_id == SCHEMA_ID_V3:
            primary_question = figure.get("primary_question")
            if not isinstance(primary_question, str) or not primary_question.strip():
                error("BRIEF-PRIMARY-QUESTION", f"图{number} 缺少唯一 primary_question")
            elif any(separator in primary_question for separator in ("；", ";", "以及", "同时")):
                warning("BRIEF-PRIMARY-QUESTION", f"图{number} primary_question 可能包含多个并列任务，应复核是否拆图")
            if figure.get("reading_direction") not in {"left_to_right", "top_to_bottom"}:
                error("BRIEF-READING-DIRECTION", f"图{number} reading_direction 无效")
            layers = figure.get("layers")
            if not isinstance(layers, list) or not layers:
                error("BRIEF-LAYERS", f"图{number} layers 必须是非空数组")
                layers = []
            orders: set[int] = set()
            for layer in layers:
                if not isinstance(layer, dict):
                    error("BRIEF-LAYERS", f"图{number} 存在非对象层级")
                    continue
                layer_id, order = layer.get("id"), layer.get("order")
                if not isinstance(layer_id, str) or not ID_RE.fullmatch(layer_id) or layer_id in layer_ids:
                    error("BRIEF-LAYERS", f"图{number} 层级 ID 缺失、非法或重复：{layer_id}")
                else:
                    layer_ids.add(layer_id)
                if not isinstance(order, int) or isinstance(order, bool) or order < 1 or order in orders:
                    error("BRIEF-LAYERS", f"图{number} 层级 order 必须为不重复正整数：{order}")
                else:
                    orders.add(order)
            if orders and orders != set(range(1, len(orders) + 1)):
                error("BRIEF-LAYERS", f"图{number} 层级 order 必须从1连续编号")

        elements = figure.get("elements")
        if not isinstance(elements, list) or not elements:
            error("BRIEF-ELEMENTS", f"图{number} elements 必须是非空数组")
            elements = []
        element_ids: set[str] = set()
        component_marks: set[str] = set()
        step_marks: set[str] = set()
        for item in elements:
            if not isinstance(item, dict):
                error("BRIEF-ELEMENTS", f"图{number} 存在非对象元素")
                continue
            eid, label, kind = item.get("id"), item.get("label"), item.get("kind")
            if not isinstance(eid, str) or not ID_RE.fullmatch(eid) or eid in element_ids:
                error("BRIEF-ELEMENTS", f"图{number} 元素 ID 缺失、非法或重复：{eid}")
                continue
            element_ids.add(eid)
            if schema_id == SCHEMA_ID_V3 and item.get("layer_id") not in layer_ids:
                error("BRIEF-LAYERS", f"图{number} 元素 {eid} 引用了未知 layer_id：{item.get('layer_id')}")
            if not isinstance(label, str) or not label.strip():
                error("BRIEF-ELEMENTS", f"图{number} 元素 {eid} 缺少 label")
            anchor = item.get("source_anchor")
            if not isinstance(anchor, str) or not anchor.strip():
                error("BRIEF-EVIDENCE", f"图{number} 元素 {eid} 缺少 source_anchor")
            elif source_corpus and anchor not in source_corpus:
                error("BRIEF-EVIDENCE", f"图{number} 元素 {eid} 的 source_anchor 在冻结来源中找不到：{anchor}")
            mark = item.get("reference_sign")
            if kind == "component":
                if not isinstance(mark, str) or not COMPONENT_RE.fullmatch(mark) or mark in component_marks:
                    error("BRIEF-MARK", f"图{number} 部件 {eid} 的数字标记无效或重复：{mark}")
                else:
                    component_marks.add(mark)
            elif kind == "step":
                if not isinstance(mark, str) or not STEP_RE.fullmatch(mark) or mark in step_marks:
                    error("BRIEF-MARK", f"图{number} 步骤 {eid} 的 Sxxx 标记无效或重复：{mark}")
                else:
                    step_marks.add(mark)
        if component_marks & step_marks:
            error("BRIEF-MARK", f"图{number} 部件标记与步骤号发生冲突")

        relation_ids: set[str] = set()
        route_channels: set[str] = set()
        relations = figure.get("relations") or []
        for relation in relations:
            if not isinstance(relation, dict):
                error("BRIEF-RELATION", f"图{number} 存在非对象关系")
                continue
            rid = relation.get("id")
            if not isinstance(rid, str) or not ID_RE.fullmatch(rid) or rid in relation_ids:
                error("BRIEF-RELATION", f"图{number} 关系 ID 缺失、非法或重复：{rid}")
                continue
            relation_ids.add(rid)
            if schema_id == SCHEMA_ID_V3:
                channel = relation.get("route_channel")
                if not isinstance(channel, str) or not ID_RE.fullmatch(channel) or channel in route_channels:
                    error("BRIEF-ROUTE-CHANNEL", f"图{number} 关系 {rid} 缺少独立 route_channel 或通道重复：{channel}")
                else:
                    route_channels.add(channel)
                feature_ids = relation.get("source_feature_ids")
                if not isinstance(feature_ids, list) or not feature_ids or any(not isinstance(fid, str) or not re.fullmatch(r"F\d{3}", fid) for fid in feature_ids):
                    error("BRIEF-EVIDENCE", f"图{number} 关系 {rid} 必须登记 source_feature_ids")
            source, target = relation.get("source"), relation.get("target")
            if source not in element_ids or target not in element_ids:
                error("BRIEF-RELATION", f"图{number} 关系 {rid} 引用了未知元素：{source}→{target}")
            if source == target:
                error("BRIEF-RELATION", f"图{number} 关系 {rid} 不得自环")
            if relation.get("preferred_direction") not in {"vertical", "horizontal", "auto"}:
                error("BRIEF-RELATION", f"图{number} 关系 {rid} preferred_direction 无效")
            if relation.get("direct_connection_required") is not True:
                error("BRIEF-RELATION", f"图{number} 关系 {rid} 的 direct_connection_required 必须为 true")
            anchor = relation.get("source_anchor")
            if not isinstance(anchor, str) or not anchor.strip():
                error("BRIEF-EVIDENCE", f"图{number} 关系 {rid} 缺少 source_anchor")
            elif source_corpus and anchor not in source_corpus:
                error("BRIEF-EVIDENCE", f"图{number} 关系 {rid} 的 source_anchor 在冻结来源中找不到：{anchor}")

        if schema_id == SCHEMA_ID_V3:
            budget = figure.get("complexity_budget")
            if not isinstance(budget, dict):
                error("BRIEF-COMPLEXITY", f"图{number} 缺少 complexity_budget")
                budget = {}
            decisions = sum(1 for item in elements if isinstance(item, dict) and item.get("kind") == "decision")
            for field, actual in (
                ("max_technical_elements", len(elements)),
                ("max_relations", len(relations)),
                ("max_decisions", decisions),
            ):
                limit = budget.get(field)
                if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                    error("BRIEF-COMPLEXITY", f"图{number} {field} 必须是非负整数")
                elif actual > limit:
                    error("BRIEF-COMPLEXITY", f"图{number} {field} 预算 {limit}，实际 {actual}；应拆图而非继续堆叠")

            normal_exits = figure.get("normal_exit_ids")
            exception_exits = figure.get("exception_exit_ids")
            if not isinstance(normal_exits, list) or not normal_exits:
                error("BRIEF-EXIT", f"图{number} 必须登记至少一个正常出口")
                normal_exits = []
            if not isinstance(exception_exits, list):
                error("BRIEF-EXIT", f"图{number} exception_exit_ids 必须是数组")
                exception_exits = []
            for exit_id in normal_exits + exception_exits:
                if exit_id not in element_ids:
                    error("BRIEF-EXIT", f"图{number} 出口 {exit_id} 不是已登记元素")
            if set(normal_exits) & set(exception_exits):
                error("BRIEF-EXIT", f"图{number} 正常出口与异常出口不得重叠")

            assertions = figure.get("spec_assertions")
            if not isinstance(assertions, list) or not assertions:
                error("BRIEF-SPEC-ASSERTION", f"图{number} 缺少 spec_assertions")
                assertions = []
            covered_elements: set[str] = set()
            covered_relations: set[str] = set()
            specification_text = source_text_by_id.get("specification", "")
            for assertion_index, assertion in enumerate(assertions, start=1):
                if not isinstance(assertion, dict):
                    error("BRIEF-SPEC-ASSERTION", f"图{number} 第 {assertion_index} 条正文声明不是对象")
                    continue
                anchor = assertion.get("anchor")
                if not isinstance(anchor, str) or not anchor.strip() or anchor not in specification_text:
                    error("BRIEF-SPEC-ASSERTION", f"图{number} 第 {assertion_index} 条正文声明锚点无法在说明书中定位：{anchor}")
                assertion_elements = assertion.get("element_ids")
                assertion_relations = assertion.get("relation_ids")
                if not isinstance(assertion_elements, list) or not isinstance(assertion_relations, list):
                    error("BRIEF-SPEC-ASSERTION", f"图{number} 第 {assertion_index} 条正文声明必须提供 element_ids 和 relation_ids 数组")
                    continue
                unknown_elements = set(assertion_elements) - element_ids
                unknown_relations = set(assertion_relations) - relation_ids
                if unknown_elements:
                    error("BRIEF-SPEC-ASSERTION", f"图{number} 正文声明引用未知元素：{sorted(unknown_elements)}")
                if unknown_relations:
                    error("BRIEF-SPEC-ASSERTION", f"图{number} 正文声明引用未知关系：{sorted(unknown_relations)}")
                covered_elements.update(assertion_elements)
                covered_relations.update(assertion_relations)
            technical_elements = {
                item["id"] for item in elements
                if isinstance(item, dict) and item.get("kind") not in {"annotation", "start_end"} and isinstance(item.get("id"), str)
            }
            if technical_elements - covered_elements:
                error("BRIEF-SPEC-ASSERTION", f"图{number} 有技术元素未被说明书图示声明覆盖：{sorted(technical_elements - covered_elements)}")
            if relation_ids - covered_relations:
                error("BRIEF-SPEC-ASSERTION", f"图{number} 有技术关系未被说明书图示声明覆盖：{sorted(relation_ids - covered_relations)}")

        outputs = figure.get("outputs")
        resolved_outputs: dict[str, str] = {}
        if not isinstance(outputs, dict):
            error("BRIEF-OUTPUT", f"图{number} 缺少 outputs")
            outputs = {}
        for key in ("drawio", "preview_png", "final_png", "export_report"):
            raw = outputs.get(key)
            if not isinstance(raw, str) or not raw:
                error("BRIEF-OUTPUT", f"图{number} 缺少 outputs.{key}")
                continue
            try:
                path = resolve_under(case_dir, raw, f"图{number} outputs.{key}")
                resolved_outputs[key] = str(path)
                if key in {"drawio", "final_png"} and output_root is not None:
                    try:
                        path.relative_to(output_root)
                    except ValueError:
                        error("BRIEF-OUTPUT", f"图{number} {key} 必须位于 output_root 内")
            except ValueError as exc:
                error("BRIEF-OUTPUT", str(exc))
        figure_reports.append({
            "figure_number": number,
            "elements": len(elements),
            "relations": len(figure.get("relations") or []),
            "component_marks": sorted(component_marks),
            "step_marks": sorted(step_marks),
            "outputs": resolved_outputs,
        })
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        error("BRIEF-NUMBERING", f"图号必须从1连续排列，实际为 {numbers}")

    return {
        "schema_id": "cn-patent-drawing-brief-validation/v2",
        "brief": str(brief_path.resolve()),
        "brief_sha256": sha256(brief_path),
        "case_dir": str(case_dir),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "evidence_scope": {
            "proves": ["绘图合同字段、来源哈希、元素关系引用和输出路径可复算", "v3 的阅读层级、复杂度预算、出口和正文图示声明满足结构合同"],
            "does_not_prove": ["最终 PNG 不存在视觉缺陷", "图示技术关系具有法律支持或创造性"],
        },
        "sources": bound_sources,
        "figures": figure_reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验中国专利附图交接合同")
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate_brief(args.brief.resolve(), args.case_dir.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        report = {"schema_id": "cn-patent-drawing-brief-validation/v2", "status": "FAIL", "errors": [{"code": "BRIEF-INPUT", "message": str(exc)}], "warnings": []}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
