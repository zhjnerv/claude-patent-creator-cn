#!/usr/bin/env python3
"""比较原始 Draw.io 与用户修改范例，提取视觉样式并隔离技术/结构变化。"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_ID = "cn-patent-drawing-style-brief/v1"
MARK_RE = re.compile(r"(?:^|\s)((?:S\d+)|(?:\d{2,4}))(?:\s|：|:|$)", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return text.replace("\xa0", " ").strip()


def compact(value: str) -> str:
    return re.sub(r"[\s，,；;。:：()（）]", "", plain_text(value)).lower()


def style_dict(value: str) -> dict[str, str]:
    return {key: item for part in (value or "").split(";") if "=" in part for key, item in [part.split("=", 1)]}


def geometry(cell: ET.Element) -> dict[str, float]:
    node = cell.find("mxGeometry")
    result: dict[str, float] = {}
    if node is None:
        return result
    for key in ("x", "y", "width", "height"):
        try:
            result[key] = float(node.get(key, "0"))
        except ValueError:
            pass
    return result


def normalized_cells(path: Path) -> tuple[ET.Element, list[dict[str, Any]]]:
    root = ET.parse(path).getroot()
    model = root.find("diagram/mxGraphModel") if root.tag == "mxfile" else root
    if model is None or model.find("root") is None:
        raise ValueError(f"缺少 mxGraphModel/root：{path}")
    cells: list[dict[str, Any]] = []
    root_node = model.find("root")
    if root_node is None:
        raise ValueError(f"缺少 mxGraphModel/root：{path}")
    for child in root_node:
        wrapper = child if child.tag != "mxCell" else None
        cell = child if child.tag == "mxCell" else child.find("mxCell")
        if cell is None:
            continue
        cid = (wrapper.get("id") if wrapper is not None else None) or cell.get("id", "")
        value = (wrapper.get("label") if wrapper is not None else None) or cell.get("value", "")
        cells.append({
            "id": cid,
            "value": value,
            "text": plain_text(value),
            "compact": compact(value),
            "mark": (MARK_RE.search(plain_text(value)).group(1).upper() if MARK_RE.search(plain_text(value)) else None),
            "vertex": cell.get("vertex") == "1",
            "edge": cell.get("edge") == "1",
            "source": cell.get("source"),
            "target": cell.get("target"),
            "style": style_dict(cell.get("style", "")),
            "geometry": geometry(cell),
        })
    return model, cells


def match_nodes(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    old_nodes = [item for item in old if item["vertex"] and item["id"] not in {"0", "1"}]
    new_nodes = [item for item in new if item["vertex"] and item["id"] not in {"0", "1"}]
    unmatched_old = {item["id"]: item for item in old_nodes}
    unmatched_new = {item["id"]: item for item in new_nodes}
    matches: list[dict[str, Any]] = []

    def bind(left: dict[str, Any], right: dict[str, Any], method: str) -> None:
        matches.append({"baseline": left, "reference": right, "method": method})
        unmatched_old.pop(left["id"], None)
        unmatched_new.pop(right["id"], None)

    for cid in sorted(set(unmatched_old) & set(unmatched_new)):
        bind(unmatched_old[cid], unmatched_new[cid], "stable_id")
    for field, method in (("mark", "reference_sign"), ("compact", "visible_label")):
        old_index: dict[str, list[dict[str, Any]]] = {}
        new_index: dict[str, list[dict[str, Any]]] = {}
        for item in unmatched_old.values():
            if item[field]: old_index.setdefault(item[field], []).append(item)
        for item in unmatched_new.values():
            if item[field]: new_index.setdefault(item[field], []).append(item)
        for key in sorted(set(old_index) & set(new_index)):
            if len(old_index[key]) == len(new_index[key]) == 1:
                bind(old_index[key][0], new_index[key][0], method)
    return matches, list(unmatched_old.values()), list(unmatched_new.values())


def relation_signatures(cells: list[dict[str, Any]], node_names: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for item in cells:
        if not item["edge"]:
            continue
        result.append({
            "id": item["id"],
            "source_id": item["source"],
            "target_id": item["target"],
            "source": node_names.get(item["source"], item["source"]),
            "target": node_names.get(item["target"], item["target"]),
            "label": compact(item["value"]),
            "raw_label": item["text"],
        })
    return result


def mode(values: list[Any]) -> Any:
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def numeric_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"minimum": min(values), "median": statistics.median(values), "maximum": max(values)}


def layout_profile(model: ET.Element, nodes: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item["id"]: item for item in nodes}
    vertical = horizontal = diagonal = 0
    for relation in relations:
        source, target = by_id.get(relation.get("source_id")), by_id.get(relation.get("target_id"))
        if not source or not target:
            continue
        sg, tg = source["geometry"], target["geometry"]
        if not all(key in sg and key in tg for key in ("x", "y", "width", "height")):
            continue
        sx, sy = sg["x"] + sg["width"] / 2, sg["y"] + sg["height"] / 2
        tx, ty = tg["x"] + tg["width"] / 2, tg["y"] + tg["height"] / 2
        if abs(ty - sy) > abs(tx - sx) * 1.25: vertical += 1
        elif abs(tx - sx) > abs(ty - sy) * 1.25: horizontal += 1
        else: diagonal += 1
    orientation = "top_to_bottom" if vertical >= horizontal else "left_to_right"
    return {
        "reading_direction": orientation,
        "main_flow_alignment": "center",
        "sibling_layout": "horizontal" if orientation == "top_to_bottom" else "vertical",
        "convergence": "return_to_main_axis",
        "edge_direction_counts": {"vertical": vertical, "horizontal": horizontal, "diagonal": diagonal},
        "page_width": float(model.get("pageWidth", "0")),
        "page_height": float(model.get("pageHeight", "0")),
    }


def analyze(baseline: Path, reference: Path, case_dir: Path, case_id: str, approved_by: str | None) -> dict[str, Any]:
    baseline_model, baseline_cells = normalized_cells(baseline)
    reference_model, reference_cells = normalized_cells(reference)
    matches, old_unmatched, new_unmatched = match_nodes(baseline_cells, reference_cells)
    match_old_to_new = {item["baseline"]["id"]: item["reference"]["id"] for item in matches}
    baseline_names = {item["id"]: item["compact"] for item in baseline_cells if item["vertex"]}
    reference_names = {item["id"]: item["compact"] for item in reference_cells if item["vertex"]}
    baseline_relations = relation_signatures(baseline_cells, baseline_names)
    reference_relations = relation_signatures(reference_cells, reference_names)
    baseline_rel_set = {(x["source"], x["target"], x["label"]) for x in baseline_relations}
    reference_rel_set = {(x["source"], x["target"], x["label"]) for x in reference_relations}

    anomalies = []
    for relation in reference_relations:
        if not relation["source"] or not relation["target"]:
            anomalies.append({
                "code": "STYLE-REFERENCE-ABSOLUTE-ENDPOINT",
                "severity": "hard",
                "subject": relation["id"],
                "message": "范例关系缺少 source 或 target，已成为绝对端点；只能学习视觉位置，不能复制该拓扑。",
            })
    duplicated_labels = [key for key, count in Counter(item["compact"] for item in reference_cells if item["vertex"] and item["compact"]).items() if count > 1]
    for label in duplicated_labels:
        anomalies.append({"code": "STYLE-REFERENCE-DUPLICATE-LABEL", "severity": "warning", "subject": label, "message": "范例存在重复可见标签，标签匹配可能产生歧义。"})

    visual_changes = []
    style_keys = ("shape", "rounded", "dashed", "fillColor", "strokeColor", "fontFamily", "fontSize", "strokeWidth")
    for item in matches:
        left, right = item["baseline"], item["reference"]
        changed = {}
        if left["geometry"] != right["geometry"]:
            changed["geometry"] = {"from": left["geometry"], "to": right["geometry"]}
        style_change = {key: {"from": left["style"].get(key), "to": right["style"].get(key)} for key in style_keys if left["style"].get(key) != right["style"].get(key)}
        if style_change: changed["style"] = style_change
        if changed:
            visual_changes.append({"baseline_id": left["id"], "reference_id": right["id"], "label": right["text"], "changes": changed})

    reference_nodes = [item for item in reference_cells if item["vertex"] and item["id"] not in {"0", "1"}]
    reference_edges = [item for item in reference_cells if item["edge"]]
    widths = [item["geometry"].get("width") for item in reference_nodes if item["geometry"].get("width") is not None]
    heights = [item["geometry"].get("height") for item in reference_nodes if item["geometry"].get("height") is not None]
    font_sizes = [float(item["style"]["fontSize"]) for item in reference_nodes if item["style"].get("fontSize", "").replace(".", "", 1).isdigit()]
    reusable_style = {
        "page": {"width": float(reference_model.get("pageWidth", "0")), "height": float(reference_model.get("pageHeight", "0"))},
        "grid_size": int(float(reference_model.get("gridSize", "10"))),
        "layout": layout_profile(reference_model, reference_nodes, reference_relations),
        "typography": {"font_family": mode([item["style"].get("fontFamily") for item in reference_nodes if item["style"].get("fontFamily")]), "font_size": mode(font_sizes), "all_font_sizes": sorted(set(font_sizes))},
        "node_geometry": {"width": numeric_summary(widths), "height": numeric_summary(heights), "same_level_similar_size": True, "fit_text_before_shrinking_font": True},
        "palette": {"fill_colors": sorted({item["style"].get("fillColor") for item in reference_nodes if item["style"].get("fillColor")}), "stroke_colors": sorted({item["style"].get("strokeColor") for item in reference_nodes if item["style"].get("strokeColor")})},
        "edge_style": {"edge_style": mode([item["style"].get("edgeStyle") for item in reference_edges if item["style"].get("edgeStyle")]), "rounded": mode([item["style"].get("rounded") for item in reference_edges if item["style"].get("rounded")]), "end_arrow": mode([item["style"].get("endArrow") for item in reference_edges if item["style"].get("endArrow")]), "stroke_width": mode([item["style"].get("strokeWidth") for item in reference_edges if item["style"].get("strokeWidth")]), "native_edge_labels": True},
    }
    technical_diff = {
        "added_nodes": [{"id": item["id"], "label": item["text"]} for item in new_unmatched],
        "removed_nodes": [{"id": item["id"], "label": item["text"]} for item in old_unmatched],
        "renamed_nodes": [{"baseline_id": item["baseline"]["id"], "reference_id": item["reference"]["id"], "from": item["baseline"]["text"], "to": item["reference"]["text"]} for item in matches if item["baseline"]["compact"] != item["reference"]["compact"]],
        "added_relations": [list(item) for item in sorted(reference_rel_set - baseline_rel_set, key=str)],
        "removed_relations": [list(item) for item in sorted(baseline_rel_set - reference_rel_set, key=str)],
        "endpoint_changes": [],
    }
    has_technical = any(technical_diff[key] for key in technical_diff)
    anomaly_codes = sorted({item["code"] for item in anomalies})
    approval = {
        "status": "approved" if approved_by else "pending",
        "approved_visual_only": bool(approved_by),
        "acknowledged_anomaly_codes": anomaly_codes if approved_by else [],
    }
    if approved_by:
        approval.update({"approved_by": approved_by, "approved_at": datetime.now(timezone.utc).isoformat()})
    return {
        "schema_id": SCHEMA_ID,
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_drawio": {"path": baseline.resolve().relative_to(case_dir.resolve()).as_posix(), "sha256": sha256(baseline)},
        "reference_drawio": {"path": reference.resolve().relative_to(case_dir.resolve()).as_posix(), "sha256": sha256(reference)},
        "analysis_status": "REVIEW_REQUIRED" if has_technical or anomalies else "CLEAN_VISUAL_ONLY",
        "matching": {"strategy": "stable_id_then_reference_sign_then_visible_label", "matched_nodes": [{"baseline_id": item["baseline"]["id"], "reference_id": item["reference"]["id"], "label": item["reference"]["text"], "method": item["method"]} for item in matches], "unmatched_baseline_nodes": [item["text"] for item in old_unmatched], "unmatched_reference_nodes": [item["text"] for item in new_unmatched]},
        "technical_diff": technical_diff,
        "visual_diff": {"page": {"from": {"width": baseline_model.get("pageWidth"), "height": baseline_model.get("pageHeight"), "grid_size": baseline_model.get("gridSize")}, "to": {"width": reference_model.get("pageWidth"), "height": reference_model.get("pageHeight"), "grid_size": reference_model.get("gridSize")}}, "changed_nodes": visual_changes},
        "structural_anomalies": anomalies,
        "reusable_style": reusable_style,
        "application_policy": {"visual_only": True, "preserve_stable_ids": True, "preserve_element_labels": True, "preserve_relation_ids": True, "preserve_relation_endpoints": True, "preserve_method_topology": True},
        "approval": approval,
    }


def validate_style_brief(path: Path, case_dir: Path, require_approved: bool = True) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if value.get("schema_id") != SCHEMA_ID:
        errors.append({"code": "STYLE-BRIEF-SCHEMA", "message": f"schema_id 必须为 {SCHEMA_ID}"})
    for key in ("baseline_drawio", "reference_drawio"):
        artifact = value.get(key) or {}
        raw = artifact.get("path")
        if not isinstance(raw, str) or not raw:
            errors.append({"code": "STYLE-BRIEF-ARTIFACT", "message": f"缺少 {key}.path"})
            continue
        candidate = (case_dir / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            candidate.relative_to(case_dir.resolve())
        except ValueError:
            errors.append({"code": "STYLE-BRIEF-PATH", "message": f"{key} 必须位于案件目录内"})
            continue
        if not candidate.is_file():
            errors.append({"code": "STYLE-BRIEF-MISSING", "message": f"文件不存在：{candidate}"})
        elif artifact.get("sha256") != sha256(candidate):
            errors.append({"code": "STYLE-BRIEF-STALE", "message": f"{key} SHA-256 已陈旧"})
    policy = value.get("application_policy") or {}
    for key in ("visual_only", "preserve_stable_ids", "preserve_element_labels", "preserve_relation_ids", "preserve_relation_endpoints", "preserve_method_topology"):
        if policy.get(key) is not True:
            errors.append({"code": "STYLE-BRIEF-POLICY", "message": f"application_policy.{key} 必须为 true"})
    approval = value.get("approval") or {}
    if require_approved and (approval.get("status") != "approved" or approval.get("approved_visual_only") is not True):
        errors.append({"code": "STYLE-BRIEF-APPROVAL", "message": "样式合同尚未批准为仅视觉复用"})
    anomaly_codes = {item.get("code") for item in value.get("structural_anomalies") or [] if isinstance(item, dict)}
    acknowledged = set(approval.get("acknowledged_anomaly_codes") or [])
    if require_approved and not anomaly_codes <= acknowledged:
        errors.append({"code": "STYLE-BRIEF-ANOMALY", "message": f"未确认范例异常：{sorted(anomaly_codes - acknowledged)}"})
    return {"schema_id": "cn-patent-drawing-style-brief-validation/v1", "style_brief": str(path.resolve()), "style_brief_sha256": sha256(path), "status": "PASS" if not errors else "FAIL", "errors": errors, "analysis_status": value.get("analysis_status"), "approval": approval}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--approve-by", help="仅在用户已明确确认视觉意图后填写")
    args = parser.parse_args(argv)
    try:
        payload = analyze(args.baseline.resolve(), args.reference.resolve(), args.case_dir.resolve(), args.case_id, args.approve_by)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"schema_id": SCHEMA_ID, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
