#!/usr/bin/env python3
"""独立验证中国专利 Draw.io 附图、官方导出和视觉复核证据。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BRIEF_VALIDATOR = SCRIPT_DIR / "validate_drawing_brief.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


brief_validator = load_module(BRIEF_VALIDATOR, "patent_drawing_brief_validator")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{label}含 BOM")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}顶层必须是对象")
    return value


def resolve_under(case_dir: Path, raw: str, label: str) -> Path:
    candidate = Path(raw)
    candidate = candidate.resolve() if candidate.is_absolute() else (case_dir / candidate).resolve()
    try:
        candidate.relative_to(case_dir)
    except ValueError as exc:
        raise ValueError(f"{label}必须位于案件目录内：{raw}") from exc
    return candidate


def parse_style(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in (value or "").split(";"):
        if "=" in part:
            key, item = part.split("=", 1)
            result[key] = item
    return result


def plain_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&nbsp;", " ").strip()


def rect(cell: ET.Element) -> tuple[float, float, float, float] | None:
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return None
    try:
        return (
            float(geometry.get("x", "0")), float(geometry.get("y", "0")),
            float(geometry.get("width", "0")), float(geometry.get("height", "0")),
        )
    except ValueError:
        return None


def explicit_points(edge: ET.Element) -> list[tuple[float, float]]:
    geometry = edge.find("mxGeometry")
    if geometry is None:
        return []
    array = geometry.find("Array[@as='points']")
    if array is None:
        return []
    result = []
    for point in array.findall("mxPoint"):
        try:
            result.append((float(point.get("x", "0")), float(point.get("y", "0"))))
        except ValueError:
            pass
    return result


def normalize_color(value: str | None) -> str | None:
    if not value or value.lower() in {"none", "transparent", "default"}:
        return None
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        return value.upper()
    return value.upper()


def find_drawio_skill(raw: Path | None) -> Path:
    candidates = [
        raw,
        Path.home() / ".codex/skills/drawio-skill",
        Path.home() / ".claude/skills/drawio-skill",
        Path.home() / ".cc-switch/skills/drawio-skill",
    ]
    for candidate in candidates:
        if candidate and (candidate / "scripts/validate.py").is_file():
            return candidate.resolve()
    raise FileNotFoundError("未找到 drawio-skill/scripts/validate.py")


def run_drawio_lint(drawio_skill: Path, drawing: Path) -> dict[str, Any]:
    command = [sys.executable, str(drawio_skill / "scripts/validate.py"), str(drawing), "--strict", "--json"]
    # Draw.io 在 Windows 下可能仍向 stderr 输出系统代码页字节；使用替换策略
    # 保留 lint 退出码和 JSON 标准输出，避免解码异常掩盖真正的结构检查结果。
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"errors": 1, "warnings": 0, "findings": [{"code": "LINT-OUTPUT", "message": result.stdout + result.stderr}]}
    return {"command": command, "exit_code": result.returncode, "report": payload}


def png_info(path: Path) -> dict[str, Any]:
    exporter = load_module(SCRIPT_DIR / "export_patent_drawio.py", "patent_drawio_export_inspector")
    return exporter.inspect_png(path)


def verify_drawio(
    path: Path,
    figure: dict[str, Any],
    color_policy: dict[str, Any],
    drawio_skill: Path,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []

    def error(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    root = ET.parse(path).getroot()
    if root.tag != "mxfile" or root.get("compressed") != "false":
        error("DRAWING-XML", "必须是 mxfile compressed=false")
    diagrams = root.findall("diagram")
    if len(diagrams) != 1:
        error("DRAWING-PAGE", "每个专利附图母版必须恰好一页")
        model = None
    else:
        model = diagrams[0].find("mxGraphModel")
    if model is None or model.find("root") is None:
        error("DRAWING-XML", "缺少 mxGraphModel/root")
        return {"path": str(path), "sha256": sha256(path), "errors": errors, "passed": False}

    cells = model.findall("./root/mxCell")
    by_id = {cell.get("id", ""): cell for cell in cells}
    vertices = {key: cell for key, cell in by_id.items() if cell.get("vertex") == "1"}
    edges = {key: cell for key, cell in by_id.items() if cell.get("edge") == "1"}
    element_ids = {item["id"] for item in figure["elements"]}
    relation_ids = {item["id"] for item in figure["relations"]}

    for eid in element_ids:
        if eid not in vertices:
            error("DRAWING-ELEMENT", f"合同元素未出现在 drawio：{eid}")
    allowed_vertex_ids = element_ids | {f"label-{rid}" for rid in relation_ids}
    for vid, cell in vertices.items():
        if vid in {"0", "1"}:
            continue
        if vid not in allowed_vertex_ids and not vid.startswith(("container-", "frame-", "decor-")):
            error("DRAWING-EXTRA", f"图中存在合同外的可见/技术节点：{vid}")

    for item in figure["elements"]:
        cell = vertices.get(item["id"])
        if cell is None:
            continue
        text = plain_text(cell.get("value", ""))
        if item["label"] not in text:
            error("DRAWING-LABEL", f"元素 {item['id']} 缺少合同标签：{item['label']}")
        mark = item.get("reference_sign")
        if mark and mark not in text:
            error("DRAWING-MARK", f"元素 {item['id']} 缺少标记：{mark}")

    visible_text_ids = {
        vid for vid, cell in vertices.items()
        if "text;" in cell.get("style", "") and plain_text(cell.get("value", ""))
    }
    for edge_id, edge in edges.items():
        if edge.get("value", "").strip():
            error("DRAWING-EDGE-LABEL", f"边 {edge_id} 直接携带文字")
        if edge.get("source") in visible_text_ids or edge.get("target") in visible_text_ids:
            error("DRAWING-TEXT-WAYPOINT", f"边 {edge_id} 使用可见文字节点作为端点")
        if edge_id not in relation_ids:
            error("DRAWING-EXTRA", f"图中存在合同外技术关系：{edge_id}")
        if "edgeStyle=orthogonalEdgeStyle" not in edge.get("style", ""):
            error("DRAWING-ROUTE", f"边 {edge_id} 不是正交连接")

    for relation in figure["relations"]:
        edge = edges.get(relation["id"])
        if edge is None:
            error("DRAWING-RELATION", f"合同关系未出现在 drawio：{relation['id']}")
            continue
        if edge.get("source") != relation["source"] or edge.get("target") != relation["target"]:
            error("DRAWING-RELATION", f"关系 {relation['id']} 的 source/target 与合同不一致")
        label = relation.get("label", "").strip()
        label_id = f"label-{relation['id']}"
        if label:
            label_cell = vertices.get(label_id)
            if label_cell is None or plain_text(label_cell.get("value", "")) != label:
                error("DRAWING-RELATION-LABEL", f"关系 {relation['id']} 缺少旁置标签节点 {label_id}")
            if any(e.get("source") == label_id or e.get("target") == label_id for e in edges.values()):
                error("DRAWING-TEXT-WAYPOINT", f"关系标签 {label_id} 被用于路由")
        elif label_id in vertices:
            error("DRAWING-RELATION-LABEL", f"无标签关系 {relation['id']} 出现多余标签节点")
        source_rect, target_rect = rect(vertices.get(relation["source"], ET.Element("x"))), rect(vertices.get(relation["target"], ET.Element("x")))
        points = explicit_points(edge)
        direction = relation.get("preferred_direction")
        if relation.get("direct_connection_required") and direction in {"vertical", "horizontal"} and source_rect and target_rect:
            sx, sy, sw, sh = source_rect; tx, ty, tw, th = target_rect
            if direction == "vertical" and abs((sx + sw / 2) - (tx + tw / 2)) > 1:
                error("DRAWING-DIRECT", f"关系 {relation['id']} 应竖直直连但节点中心未对齐")
            if direction == "horizontal" and abs((sy + sh / 2) - (ty + th / 2)) > 1:
                error("DRAWING-DIRECT", f"关系 {relation['id']} 应水平直连但节点中心未对齐")
            if points:
                error("DRAWING-DIRECT", f"关系 {relation['id']} 本应直连却设置了显式路由点")

    canvas_text = "\n".join(plain_text(cell.get("value", "")) for cell in vertices.values())
    if re.search(rf"图\s*{figure['figure_number']}(?![0-9])", canvas_text):
        error("DRAWING-FIGURE-NUMBER", "图号不得写入画布")

    allowed_fills = {normalize_color(value) for value in color_policy["allowed_fill_colors"]}
    allowed_strokes = {normalize_color(value) for value in color_policy["allowed_stroke_colors"]}
    nonwhite_fills: set[str] = set()
    for vid, cell in vertices.items():
        style = parse_style(cell.get("style", ""))
        fill = normalize_color(style.get("fillColor"))
        stroke = normalize_color(style.get("strokeColor"))
        if fill and fill not in allowed_fills:
            error("DRAWING-COLOR", f"节点 {vid} 使用未授权填充色：{fill}")
        if stroke and stroke not in allowed_strokes:
            error("DRAWING-COLOR", f"节点 {vid} 使用未授权边框色：{stroke}")
        if fill and fill not in {"#FFFFFF", "#F4F4F4", "#F5F5F5"}:
            nonwhite_fills.add(fill)
        if style.get("gradientColor") not in {None, "none"}:
            error("DRAWING-COLOR", f"节点 {vid} 使用渐变")
        if style.get("shadow") == "1" or style.get("sketch") == "1":
            error("DRAWING-COLOR", f"节点 {vid} 使用阴影或手绘效果")
    if len(nonwhite_fills) > color_policy["max_nonwhite_fills"]:
        error("DRAWING-COLOR", f"非白填充色超过上限：{sorted(nonwhite_fills)}")

    lint = run_drawio_lint(drawio_skill, path)
    if lint["exit_code"] != 0 or lint["report"].get("errors") or lint["report"].get("warnings"):
        error("DRAWING-LINT", "drawio-skill validate.py --strict 未通过")

    return {
        "path": str(path),
        "sha256": sha256(path),
        "page_name": diagrams[0].get("name") if diagrams else None,
        "vertices": len(vertices),
        "edges": len(edges),
        "nonwhite_fill_colors": sorted(nonwhite_fills),
        "drawio_skill_lint": lint,
        "errors": errors,
        "passed": not errors,
    }


def reproduce_official_export(drawio_path: Path, final_png: Path, export: dict[str, Any]) -> dict[str, Any]:
    """Re-run the official exporter and require byte-identical PNG output."""

    parameters = export.get("parameters") or {}
    width = parameters.get("width")
    dpi = parameters.get("dpi", 300)
    border = parameters.get("border", 10)
    with tempfile.TemporaryDirectory(prefix="patent_drawing_verify_") as raw:
        temp = Path(raw)
        reproduced = temp / "reproduced.png"
        report = temp / "reproduced-report.json"
        command = [
            sys.executable, str(SCRIPT_DIR / "export_patent_drawio.py"),
            "--input", str(drawio_path), "--png", str(reproduced),
            "--dpi", str(dpi), "--border", str(border), "--report", str(report),
        ]
        if isinstance(width, int) and not isinstance(width, bool) and width > 0:
            command.extend(["--width", str(width)])
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, check=False,
        )
        payload = load_json(report, "复算导出报告") if report.is_file() else {}
        return {
            "command": command,
            "exit_code": completed.returncode,
            "report": payload,
            "reproduced_sha256": sha256(reproduced) if reproduced.is_file() else None,
            "expected_sha256": sha256(final_png),
            "matched": reproduced.is_file() and sha256(reproduced) == sha256(final_png),
            "stderr_tail": completed.stderr[-1000:],
        }


def verify(brief_path: Path, case_dir: Path, drawio_skill_dir: Path | None) -> dict[str, Any]:
    brief_report = brief_validator.validate_brief(brief_path, case_dir)
    errors = list(brief_report.get("errors", []))
    brief = load_json(brief_path, "drawing-brief.json")
    brief_schema = brief.get("schema_id")
    output_schema = ({"cn-patent-drawing-brief/v4": "cn-patent-drawing-verification/v4", "cn-patent-drawing-brief/v3": "cn-patent-drawing-verification/v3"}.get(brief_schema, "cn-patent-drawing-verification/v2"))
    if errors:
        return {"schema_id": output_schema, "status": "FAIL", "errors": errors, "brief_validation": brief_report}
    drawio_skill = find_drawio_skill(drawio_skill_dir)
    visual_path = resolve_under(case_dir, brief["visual_review_path"], "visual_review_path")
    visual = load_json(visual_path, "visual-review.json")
    visual_schema = visual.get("schema_id")
    if brief_schema in {"cn-patent-drawing-brief/v3", "cn-patent-drawing-brief/v4"}:
        if visual_schema != "cn-patent-drawing-visual-review/v2":
            errors.append({"code": "DRAWING-VISUAL", "message": "v3/v4绘图合同必须使用 cn-patent-drawing-visual-review/v2"})
        if visual.get("brief_sha256") != sha256(brief_path):
            errors.append({"code": "DRAWING-VISUAL-STALE", "message": "视觉复核绑定的绘图合同已陈旧"})
        if not isinstance(visual.get("review_method"), str) or not visual["review_method"].strip():
            errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 缺少实际查看方式 review_method"})
    elif visual_schema not in {"cn-patent-drawing-visual-review/v1", "cn-patent-drawing-visual-review/v2"}:
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json schema_id 无效"})
    if not isinstance(visual.get("reviewer"), str) or not visual["reviewer"].strip():
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 缺少复核者"})
    if not isinstance(visual.get("reviewed_at"), str) or not visual["reviewed_at"].strip():
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 缺少复核时间"})
    visual_items = visual.get("figures")
    if not isinstance(visual_items, list):
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json figures 必须是数组"})
        visual_items = []
    valid_visual_items = [item for item in visual_items if isinstance(item, dict) and isinstance(item.get("figure_number"), int)]
    if len(valid_visual_items) != len(visual_items):
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 含无效图项或图号"})
    visual_by_number = {item["figure_number"]: item for item in valid_visual_items}
    if len(visual_by_number) != len(valid_visual_items):
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 含重复图号"})
    figures = []
    for figure in brief["figures"]:
        number = figure["figure_number"]
        paths = {key: resolve_under(case_dir, raw, f"图{number} {key}") for key, raw in figure["outputs"].items() if raw}
        for required in ("drawio", "preview_png", "final_png", "export_report"):
            if required not in paths or not paths[required].is_file():
                errors.append({"code": "DRAWING-ARTIFACT", "message": f"图{number} 缺少 {required}"})
        if any(required not in paths or not paths[required].is_file() for required in ("drawio", "preview_png", "final_png", "export_report")):
            continue
        drawio_report = verify_drawio(paths["drawio"], figure, brief["global_constraints"]["color_policy"], drawio_skill)
        errors.extend(drawio_report["errors"])
        export = load_json(paths["export_report"], f"图{number} export-report")
        if export.get("schema_id") != "cn-patent-drawio-export/v1":
            errors.append({"code": "DRAWING-EXPORT", "message": f"图{number} 导出报告 schema_id 无效"})
        if export.get("status") != "PASS" or (export.get("renderer") or {}).get("kind") != "drawio_desktop_cli":
            errors.append({"code": "DRAWING-EXPORT", "message": f"图{number} 未由 Draw.io Desktop CLI 正式导出"})
        if (export.get("source") or {}).get("sha256") != sha256(paths["drawio"]):
            errors.append({"code": "DRAWING-EXPORT-STALE", "message": f"图{number} 导出报告绑定的 drawio 已陈旧"})
        png = png_info(paths["final_png"])
        export_outputs = export.get("outputs") or {}
        export_png = export_outputs.get("png") or {}
        if export_png.get("sha256") != sha256(paths["final_png"]):
            errors.append({"code": "DRAWING-EXPORT-STALE", "message": f"图{number} 最终 PNG 与导出报告不一致"})
        if "svg" in paths:
            if not paths["svg"].is_file():
                errors.append({"code": "DRAWING-ARTIFACT", "message": f"图{number} 合同声明的 SVG 不存在"})
            else:
                export_svg = export_outputs.get("svg") or {}
                if export_svg.get("sha256") != sha256(paths["svg"]):
                    errors.append({"code": "DRAWING-EXPORT-STALE", "message": f"图{number} 最终 SVG 与导出报告不一致"})
        reproduced = reproduce_official_export(paths["drawio"], paths["final_png"], export)
        if reproduced["exit_code"] != 0 or not reproduced["matched"]:
            errors.append({"code": "DRAWING-EXPORT-REPRODUCE", "message": f"图{number} 无法由当前母版复算出字节一致的官方 CLI PNG"})
        minimum_dpi = brief["global_constraints"].get("minimum_png_dpi", 300)
        if not png.get("dpi") or min(png["dpi"]) + 0.2 < minimum_dpi:
            errors.append({"code": "DRAWING-DPI", "message": f"图{number} PNG DPI 不足：{png.get('dpi')}"})
        review = visual_by_number.get(number)
        if not isinstance(review, dict) or review.get("approved") is not True:
            errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 缺少批准的视觉复核"})
        else:
            try:
                reviewed_png = resolve_under(case_dir, review.get("png_path", ""), f"图{number} visual png_path")
            except ValueError as exc:
                errors.append({"code": "DRAWING-VISUAL", "message": str(exc)})
            else:
                if reviewed_png != paths["final_png"]:
                    errors.append({"code": "DRAWING-VISUAL-STALE", "message": f"图{number} 视觉复核指向的不是当前最终 PNG"})
            if review.get("png_sha256") != sha256(paths["final_png"]):
                errors.append({"code": "DRAWING-VISUAL-STALE", "message": f"图{number} 视觉复核绑定的 PNG 已陈旧"})
            if brief_schema in {"cn-patent-drawing-brief/v3", "cn-patent-drawing-brief/v4"}:
                try:
                    reviewed_export = resolve_under(case_dir, review.get("export_report_path", ""), f"图{number} visual export_report_path")
                except ValueError as exc:
                    errors.append({"code": "DRAWING-VISUAL", "message": str(exc)})
                else:
                    if reviewed_export != paths["export_report"]:
                        errors.append({"code": "DRAWING-VISUAL-STALE", "message": f"图{number} 视觉复核指向的不是当前导出报告"})
                if review.get("export_report_sha256") != sha256(paths["export_report"]):
                    errors.append({"code": "DRAWING-VISUAL-STALE", "message": f"图{number} 视觉复核绑定的导出报告已陈旧"})
                inspection = review.get("inspection")
                if not isinstance(inspection, dict):
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 缺少 inspection 观察记录"})
                    inspection = {}
                full_scale = inspection.get("full_scale_percent")
                reduced_scale = inspection.get("reduced_scale_percent")
                if not isinstance(full_scale, int) or isinstance(full_scale, bool) or full_scale < 100:
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 未记录至少 100% 比例检查"})
                if not isinstance(reduced_scale, int) or isinstance(reduced_scale, bool) or not 20 <= reduced_scale <= 80:
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 未记录 20%—80% 缩小检查"})
                if not isinstance(inspection.get("viewed_at"), str) or not inspection["viewed_at"].strip():
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 缺少实际查看时间"})
            required_checks = [
                "text_legible", "no_text_overlap", "no_edge_crossing", "no_edge_through_node",
                "no_arrow_ambiguity", "labels_adjacent", "no_unnecessary_detours",
                "consistent_typography", "balanced_spacing", "clear_visual_hierarchy",
                "formal_patent_style", "grayscale_safe", "no_figure_number_on_canvas",
            ]
            mode_check = "monochrome" if brief["global_constraints"]["color_policy"]["mode"] == "monochrome" else "restrained_color"
            required_checks.append(mode_check)
            checks = review.get("checks") or {}
            for check in required_checks:
                if checks.get(check) is not True:
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 视觉检查未通过：{check}"})
            if brief_schema in {"cn-patent-drawing-brief/v3", "cn-patent-drawing-brief/v4"}:
                observations = (review.get("inspection") or {}).get("observations")
                if not isinstance(observations, dict):
                    errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 缺少逐项 observations"})
                    observations = {}
                for check in required_checks:
                    if not isinstance(observations.get(check), str) or not observations[check].strip():
                        errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 缺少视觉检查观察记录：{check}"})
            if bool(checks.get("monochrome")) == bool(checks.get("restrained_color")):
                errors.append({"code": "DRAWING-VISUAL", "message": f"图{number} 黑白/克制彩色模式必须且只能确认一种"})
        figures.append({"figure_number": number, "drawio": drawio_report, "png": {"path": str(paths["final_png"]), **png}, "export_report": str(paths["export_report"]), "official_reexport": reproduced, "visual_review": review})
    expected_numbers = [item["figure_number"] for item in brief["figures"]]
    if sorted(visual_by_number) != expected_numbers:
        errors.append({"code": "DRAWING-VISUAL", "message": "visual-review.json 图号集合与绘图合同不一致"})
    return {
        "schema_id": output_schema,
        "brief": str(brief_path),
        "brief_sha256": sha256(brief_path),
        "drawio_skill": str(drawio_skill),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "evidence_scope": {
            "proves": ["绘图合同和来源哈希有效", "当前 Draw.io 母版可复算得到当前最终 PNG", "视觉复核记录绑定当前合同、导出报告和最终 PNG", "逐项视觉检查均有观察记录"],
            "does_not_prove": ["图示技术方案具备新颖性或创造性", "说明书和权利要求的法律支持关系已经成立", "未由复核者实际观察到的视觉事实"],
        },
        "brief_validation": brief_report,
        "figures": figures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验证中国专利 Draw.io 附图交付包")
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--drawio-skill-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify(args.brief.resolve(), args.case_dir.resolve(), args.drawio_skill_dir)
    except Exception as exc:
        report = {"schema_id": "cn-patent-drawing-verification/v2", "status": "FAIL", "errors": [{"code": "DRAWING-VERIFY-CRASH", "message": f"{type(exc).__name__}: {exc}"}], "figures": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
