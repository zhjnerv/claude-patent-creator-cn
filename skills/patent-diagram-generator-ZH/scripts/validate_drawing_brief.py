#!/usr/bin/env python3
"""校验 cn-patent-drawing-brief/v2 及其来源证据绑定。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_ID = "cn-patent-drawing-brief/v2"
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

    if brief.get("schema_id") != SCHEMA_ID:
        error("BRIEF-SCHEMA", f"schema_id 必须为 {SCHEMA_ID}")
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
            source_texts.append(path.read_text(encoding="utf-8"))
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
        for relation in figure.get("relations") or []:
            if not isinstance(relation, dict):
                error("BRIEF-RELATION", f"图{number} 存在非对象关系")
                continue
            rid = relation.get("id")
            if not isinstance(rid, str) or not ID_RE.fullmatch(rid) or rid in relation_ids:
                error("BRIEF-RELATION", f"图{number} 关系 ID 缺失、非法或重复：{rid}")
                continue
            relation_ids.add(rid)
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
        "schema_id": "cn-patent-drawing-brief-validation/v1",
        "brief": str(brief_path.resolve()),
        "brief_sha256": sha256(brief_path),
        "case_dir": str(case_dir),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
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
        report = {"schema_id": "cn-patent-drawing-brief-validation/v1", "status": "FAIL", "errors": [{"code": "BRIEF-INPUT", "message": str(exc)}], "warnings": []}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
