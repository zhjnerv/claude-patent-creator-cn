#!/usr/bin/env python3
"""验证最终附图已通过门禁，并确实作为当前图片嵌入最终 DOCX。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}顶层必须为对象")
    return value


def resolve(case_dir: Path, raw: str) -> Path:
    path = Path(raw)
    path = path.resolve() if path.is_absolute() else (case_dir / path).resolve()
    path.relative_to(case_dir.resolve())
    return path


def verify(args: argparse.Namespace) -> dict[str, Any]:
    case_dir = args.case_dir.resolve()
    brief_path = args.brief.resolve()
    brief = load(brief_path, "drawing brief")
    drawing = load(args.drawing_verification.resolve(), "drawing verification")
    docx_report = load(args.docx_report.resolve(), "DOCX report")
    docx_verification = load(args.docx_verification.resolve(), "DOCX verification")
    errors: list[dict[str, str]] = []

    if drawing.get("status") != "PASS" or drawing.get("errors"):
        errors.append({"code": "DELIVERY-DRAWING", "message": "最终附图验证未通过"})
    if drawing.get("brief_sha256") != sha256(brief_path):
        errors.append({"code": "DELIVERY-DRAWING-STALE", "message": "最终附图验证未绑定当前 drawing brief"})
    if docx_report.get("status") != "STRUCTURE_VERIFIED":
        errors.append({"code": "DELIVERY-DOCX", "message": "DOCX组装报告未通过结构验证"})
    if docx_verification.get("status") != "PASS" or docx_verification.get("errors"):
        errors.append({"code": "DELIVERY-DOCX-STALE", "message": "DOCX新鲜度验证未通过"})

    artifacts = {
        item.get("artifact_id"): item
        for item in ((docx_report.get("inputs") or {}).get("artifacts") or [])
        if isinstance(item, dict)
    }
    expected = {}
    for figure in brief.get("figures") or []:
        number = figure["figure_number"]
        png = resolve(case_dir, figure["outputs"]["final_png"])
        expected[f"figure_{number}"] = {"path": str(png), "sha256": sha256(png)}
    for artifact_id, item in expected.items():
        actual = artifacts.get(artifact_id)
        if actual is None:
            errors.append({"code": "DELIVERY-DOCX-FIGURE", "message": f"DOCX报告缺少 {artifact_id}"})
            continue
        if Path(actual.get("path", "")).resolve() != Path(item["path"]).resolve():
            errors.append({"code": "DELIVERY-DOCX-FIGURE", "message": f"{artifact_id} 路径不是当前最终PNG"})
        if actual.get("sha256") != item["sha256"]:
            errors.append({"code": "DELIVERY-DOCX-FIGURE-STALE", "message": f"{artifact_id} 哈希已陈旧"})
    actual_figure_ids = {key for key in artifacts if isinstance(key, str) and key.startswith("figure_")}
    if actual_figure_ids != set(expected):
        errors.append({"code": "DELIVERY-DOCX-FIGURE-SET", "message": f"DOCX附图集合不一致：{sorted(actual_figure_ids)} != {sorted(expected)}"})

    render = docx_report.get("render") or {}
    docx_visual = None
    if args.docx_visual_review:
        docx_visual = load(args.docx_visual_review.resolve(), "DOCX visual review")
        output_path = Path(docx_report.get("output", "")).resolve()
        if docx_visual.get("schema_id") != "cn-patent-docx-visual-review/v1":
            errors.append({"code": "DELIVERY-DOCX-VISUAL", "message": "DOCX视觉复核schema无效"})
        if docx_visual.get("approved") is not True:
            errors.append({"code": "DELIVERY-DOCX-VISUAL", "message": "DOCX视觉复核未批准"})
        if Path(docx_visual.get("docx_path", "")).resolve() != output_path or docx_visual.get("docx_sha256") != sha256(output_path):
            errors.append({"code": "DELIVERY-DOCX-VISUAL-STALE", "message": "DOCX视觉复核未绑定当前DOCX"})
        checks = docx_visual.get("checks") or {}
        for key in ("all_figures_present", "figures_legible", "figure_captions_same_page", "no_clipping", "no_abnormal_blank_pages", "abstract_figure_correct"):
            if checks.get(key) is not True:
                errors.append({"code": "DELIVERY-DOCX-VISUAL", "message": f"DOCX视觉检查未通过：{key}"})
    elif render.get("requested") is True:
        errors.append({"code": "DELIVERY-DOCX-VISUAL", "message": "已请求DOCX视觉检查，但未提供批准的视觉复核记录"})

    return {
        "schema_id": "cn-patent-drawing-docx-delivery-verification/v1",
        "status": "PASS" if not errors else "FAIL",
        "case_dir": str(case_dir),
        "brief_sha256": sha256(brief_path),
        "drawing_verification_sha256": sha256(args.drawing_verification.resolve()),
        "docx_report_sha256": sha256(args.docx_report.resolve()),
        "docx_verification_sha256": sha256(args.docx_verification.resolve()),
        "figure_count": len(expected),
        "docx_visual_review": str(args.docx_visual_review.resolve()) if args.docx_visual_review else None,
        "errors": errors,
        "evidence_scope": {
            "proves": ["当前附图验证已通过", "DOCX嵌入图片路径和SHA-256与当前最终PNG一致", "DOCX新鲜度验证已通过"],
            "does_not_prove": ["未明确请求时的DOCX逐页视觉效果", "申请文件法律实体条件"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--drawing-verification", required=True, type=Path)
    parser.add_argument("--docx-report", required=True, type=Path)
    parser.add_argument("--docx-verification", required=True, type=Path)
    parser.add_argument("--docx-visual-review", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = verify(args)
    except Exception as exc:
        report = {"schema_id": "cn-patent-drawing-docx-delivery-verification/v1", "status": "FAIL", "errors": [{"code": "DELIVERY-CRASH", "message": f"{type(exc).__name__}: {exc}"}]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
