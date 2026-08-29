"""patent-diagram-generator-ZH v2 领域合同、官方导出和历史路由缺陷回归。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "patent-diagram-generator-ZH"
BRIEF_VALIDATOR = SKILL / "scripts" / "validate_drawing_brief.py"
EXPORTER = SKILL / "scripts" / "export_patent_drawio.py"
VERIFIER = SKILL / "scripts" / "verify_patent_drawings.py"
DRAWIO_SKILL = Path.home() / ".codex/skills/drawio-skill"
STABILITY_CHECKER = SKILL / "scripts" / "check_stability_evidence.py"
STABILITY_ASSETS = SKILL / "assets" / "stability"




def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_sources(case: Path) -> dict[str, Path]:
    claims = case / "02-申请文件/权利要求书.md"
    spec = case / "02-申请文件/说明书.md"
    ledger = case / "01-检索/feature-ledger.json"
    write(claims, "# 权利要求书\n\n1. 一种方法，包括开始处理、条件校验和执行处理。\n")
    write(spec, "# 示例\n\n## 具体实施方式\n\n开始处理后执行条件校验；条件满足时执行处理。\n")
    write(ledger, json.dumps({"schema_id": "cn-patent-feature-ledger/v1", "features": [
        {"feature_id": "F001", "name": "条件校验", "classification": "distinguishing"}
    ]}, ensure_ascii=False))
    return {"claims": claims, "specification": spec, "feature_ledger": ledger}


def restrained_policy() -> dict:
    return {
        "mode": "restrained_color",
        "grayscale_safe": True,
        "color_semantics_redundant": True,
        "max_nonwhite_fills": 3,
        "allowed_fill_colors": ["#FFFFFF", "#EAF2F8", "#F8F2E6", "#F4F4F4"],
        "allowed_stroke_colors": ["#202020", "#405F73", "#706347", "#4A4A4A"],
        "palette_asset": "assets/patent-restrained-color.json",
    }


def create_brief(case: Path, sources: dict[str, Path]) -> Path:
    work = case / "03-审查工作区/附图"
    brief = work / "drawing-brief.json"
    payload = {
        "schema_id": "cn-patent-drawing-brief/v2",
        "case_id": "case-1",
        "production_skill": "drawio-skill",
        "generated_at": "2026-08-28",
        "source_artifacts": [
            {"artifact_id": key, "path": str(path.relative_to(case)), "sha256": digest(path)}
            for key, path in sources.items()
        ],
        "output_root": "02-申请文件/说明书附图",
        "global_constraints": {
            "color_policy": restrained_policy(),
            "figure_number_on_canvas": False,
            "edge_labels_allowed": False,
            "annotation_nodes_may_be_edge_endpoints": False,
            "official_drawio_export_required": True,
            "visual_review_required": True,
            "minimum_png_dpi": 300,
        },
        "visual_review_path": "03-审查工作区/附图/visual-review.json",
        "figures": [{
            "figure_number": 1,
            "title": "条件处理流程图",
            "file_stem": "图1-条件处理流程图",
            "diagram_type": "method_flowchart",
            "orientation": "portrait",
            "style_profile": "patent_restrained_color",
            "purpose": "表示条件校验和处理分支",
            "claim_numbers": [1],
            "spec_anchors": ["条件校验"],
            "elements": [
                {"id": "S100", "label": "开始处理", "kind": "start_end", "reference_sign": "S100", "source_anchor": "开始处理"},
                {"id": "S110", "label": "条件校验", "kind": "decision", "reference_sign": "S110", "source_feature_ids": ["F001"], "source_anchor": "条件校验"},
                {"id": "S120", "label": "执行处理", "kind": "step", "reference_sign": "S120", "source_anchor": "执行处理"},
            ],
            "relations": [
                {"id": "R1", "source": "S100", "target": "S110", "kind": "control", "preferred_direction": "vertical", "direct_connection_required": True, "source_anchor": "条件校验"},
                {"id": "R2", "source": "S110", "target": "S120", "label": "是", "kind": "control", "preferred_direction": "vertical", "direct_connection_required": True, "source_anchor": "条件满足时"},
            ],
            "outputs": {
                "drawio": "02-申请文件/说明书附图/图1-条件处理流程图.drawio",
                "preview_png": "03-审查工作区/附图/preview/图1-条件处理流程图.png",
                "final_png": "02-申请文件/说明书附图/图1-条件处理流程图.png",
                "svg": "02-申请文件/说明书附图/图1-条件处理流程图.svg",
                "export_report": "03-审查工作区/附图/export/图1-export.json",
            },
        }],
    }
    write(brief, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return brief


def create_valid_drawio(path: Path) -> None:
    write(path, """<mxfile compressed="false"><diagram name="条件处理流程图"><mxGraphModel pageWidth="827" pageHeight="1169"><root>
    <mxCell id="0"/><mxCell id="1" parent="0"/>
    <mxCell id="S100" value="S100&lt;br&gt;开始处理" style="ellipse;whiteSpace=wrap;html=1;fillColor=#EAF2F8;strokeColor=#405F73;fontColor=#111111;" vertex="1" parent="1"><mxGeometry x="300" y="80" width="220" height="70" as="geometry"/></mxCell>
    <mxCell id="S110" value="S110&lt;br&gt;条件校验" style="rhombus;whiteSpace=wrap;html=1;fillColor=#F8F2E6;strokeColor=#706347;fontColor=#111111;" vertex="1" parent="1"><mxGeometry x="300" y="240" width="220" height="90" as="geometry"/></mxCell>
    <mxCell id="S120" value="S120&lt;br&gt;执行处理" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#EAF2F8;strokeColor=#405F73;fontColor=#111111;" vertex="1" parent="1"><mxGeometry x="300" y="430" width="220" height="70" as="geometry"/></mxCell>
    <mxCell id="R1" edge="1" source="S100" target="S110" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=blockThin;endFill=1;" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="R2" edge="1" source="S110" target="S120" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=blockThin;endFill=1;" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="label-R2" value="是" style="text;html=1;align=center;verticalAlign=middle;fillColor=#FFFFFF;strokeColor=none;fontColor=#111111;" vertex="1" parent="1"><mxGeometry x="540" y="360" width="40" height="30" as="geometry"/></mxCell>
    </root></mxGraphModel></diagram></mxfile>""")


def test_brief_validator_binds_sources_and_rejects_stale_hash(tmp_path):
    case = tmp_path / "case"
    sources = create_sources(case)
    brief = create_brief(case, sources)
    result = run(BRIEF_VALIDATOR, "--brief", str(brief), "--case-dir", str(case))
    assert result.returncode == 0, result.stdout
    write(sources["specification"], sources["specification"].read_text(encoding="utf-8") + "已编辑")
    result = run(BRIEF_VALIDATOR, "--brief", str(brief), "--case-dir", str(case))
    assert result.returncode == 2
    assert "BRIEF-SOURCE-STALE" in result.stdout


def test_brief_validator_requires_relation_source_anchor_and_direct_edge(tmp_path):
    case = tmp_path / "case"
    sources = create_sources(case)
    brief = create_brief(case, sources)
    payload = json.loads(brief.read_text(encoding="utf-8"))
    payload["figures"][0]["relations"][0].pop("source_anchor")
    payload["figures"][0]["relations"][1]["direct_connection_required"] = False
    write(brief, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    result = run(BRIEF_VALIDATOR, "--brief", str(brief), "--case-dir", str(case))
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert any(item["code"] == "BRIEF-EVIDENCE" for item in report["errors"])
    assert any(item["code"] == "BRIEF-RELATION" for item in report["errors"])


def test_historical_source_label_target_route_is_rejected(tmp_path):
    verifier = load_module(VERIFIER, "patent_drawing_verifier_historical")
    drawing = tmp_path / "bad.drawio"
    drawing.write_text("""<mxfile compressed="false"><diagram name="bad"><mxGraphModel pageWidth="827" pageHeight="1169"><root>
    <mxCell id="0"/><mxCell id="1" parent="0"/>
    <mxCell id="S100" value="S100 开始处理" style="rounded=0;fillColor=#EAF2F8;strokeColor=#405F73;" vertex="1" parent="1"><mxGeometry x="300" y="80" width="220" height="70" as="geometry"/></mxCell>
    <mxCell id="S110" value="S110 条件校验" style="rhombus;fillColor=#F8F2E6;strokeColor=#706347;" vertex="1" parent="1"><mxGeometry x="300" y="240" width="220" height="90" as="geometry"/></mxCell>
    <mxCell id="label-R1" value="是" style="text;html=1;fillColor=#FFFFFF;strokeColor=none;" vertex="1" parent="1"><mxGeometry x="350" y="180" width="45" height="28" as="geometry"/></mxCell>
    <mxCell id="R1" edge="1" source="S100" target="label-R1" style="edgeStyle=orthogonalEdgeStyle;" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    <mxCell id="R1b" edge="1" source="label-R1" target="S110" style="edgeStyle=orthogonalEdgeStyle;" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>
    </root></mxGraphModel></diagram></mxfile>""", encoding="utf-8")
    figure = {
        "figure_number": 1,
        "elements": [
            {"id": "S100", "label": "开始处理", "reference_sign": "S100"},
            {"id": "S110", "label": "条件校验", "reference_sign": "S110"},
        ],
        "relations": [{"id": "R1", "source": "S100", "target": "S110", "label": "是", "preferred_direction": "vertical", "direct_connection_required": True}],
    }
    report = verifier.verify_drawio(drawing, figure, restrained_policy(), DRAWIO_SKILL)
    codes = {item["code"] for item in report["errors"]}
    assert "DRAWING-TEXT-WAYPOINT" in codes
    assert "DRAWING-RELATION" in codes



def test_restrained_color_policy_rejects_unapproved_flashy_fill(tmp_path):
    verifier = load_module(VERIFIER, "patent_drawing_verifier_color")
    drawing = tmp_path / "color.drawio"
    create_valid_drawio(drawing)
    text = drawing.read_text(encoding="utf-8").replace("fillColor=#EAF2F8", "fillColor=#FF0000", 1)
    drawing.write_text(text, encoding="utf-8")
    figure = {
        "figure_number": 1,
        "elements": [
            {"id": "S100", "label": "开始处理", "reference_sign": "S100"},
            {"id": "S110", "label": "条件校验", "reference_sign": "S110"},
            {"id": "S120", "label": "执行处理", "reference_sign": "S120"},
        ],
        "relations": [
            {"id": "R1", "source": "S100", "target": "S110", "preferred_direction": "vertical", "direct_connection_required": True},
            {"id": "R2", "source": "S110", "target": "S120", "label": "是", "preferred_direction": "vertical", "direct_connection_required": True},
        ],
    }
    report = verifier.verify_drawio(drawing, figure, restrained_policy(), DRAWIO_SKILL)
    assert any(item["code"] == "DRAWING-COLOR" for item in report["errors"])

@pytest.mark.skipif(shutil.which("drawio") is None and shutil.which("draw.io") is None, reason="Draw.io Desktop CLI unavailable")
def test_official_cli_export_and_final_verifier_pass(tmp_path):
    case = tmp_path / "case"
    sources = create_sources(case)
    brief = create_brief(case, sources)
    drawing = case / "02-申请文件/说明书附图/图1-条件处理流程图.drawio"
    create_valid_drawio(drawing)
    preview = case / "03-审查工作区/附图/preview/图1-条件处理流程图.png"
    final_png = case / "02-申请文件/说明书附图/图1-条件处理流程图.png"
    svg = final_png.with_suffix(".svg")
    report = case / "03-审查工作区/附图/export/图1-export.json"
    export_result = run(EXPORTER, "--input", str(drawing), "--png", str(final_png), "--svg", str(svg), "--dpi", "300", "--report", str(report))
    assert export_result.returncode == 0, export_result.stdout
    preview.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_png, preview)
    export_payload = json.loads(report.read_text(encoding="utf-8"))
    assert export_payload["renderer"]["kind"] == "drawio_desktop_cli"
    assert export_payload["source"]["sha256"] == digest(drawing)
    visual = {
        "schema_id": "cn-patent-drawing-visual-review/v1",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "test-reviewer",
        "figures": [{
            "figure_number": 1,
            "png_path": str(final_png.relative_to(case)),
            "png_sha256": digest(final_png),
            "checks": {
                "text_legible": True, "no_text_overlap": True, "no_edge_crossing": True,
                "no_edge_through_node": True, "no_arrow_ambiguity": True,
                "labels_adjacent": True, "no_unnecessary_detours": True,
                "consistent_typography": True, "balanced_spacing": True,
                "clear_visual_hierarchy": True, "formal_patent_style": True,
                "monochrome": False, "restrained_color": True,
                "grayscale_safe": True, "no_figure_number_on_canvas": True,
            },
            "approved": True,
            "notes": "official CLI fixture",
        }],
    }
    write(case / "03-审查工作区/附图/visual-review.json", json.dumps(visual, ensure_ascii=False, indent=2) + "\n")
    output = case / "03-审查工作区/附图/final-verification.json"
    result = run(VERIFIER, "--brief", str(brief), "--case-dir", str(case), "--drawio-skill-dir", str(DRAWIO_SKILL), "--output", str(output))
    assert result.returncode == 0, result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["figures"][0]["png"]["dpi"][0] == pytest.approx(300, abs=0.2)
    assert payload["figures"][0]["official_reexport"]["matched"] is True

    # Candidate binding: changing the final image invalidates both export and visual evidence.
    final_png.write_bytes(final_png.read_bytes() + b"stale")
    stale = run(VERIFIER, "--brief", str(brief), "--case-dir", str(case), "--drawio-skill-dir", str(DRAWIO_SKILL), "--output", str(output))
    assert stale.returncode == 2
    stale_payload = json.loads(output.read_text(encoding="utf-8"))
    stale_codes = {item["code"] for item in stale_payload["errors"]}
    assert "DRAWING-EXPORT-STALE" in stale_codes
    assert "DRAWING-VISUAL-STALE" in stale_codes
    assert "DRAWING-EXPORT-REPRODUCE" in stale_codes

    # Even if both JSON evidence files are forged to match the tampered PNG,
    # re-exporting the current Draw.io master must still expose the mismatch.
    export_payload["outputs"]["png"]["sha256"] = digest(final_png)
    write(report, json.dumps(export_payload, ensure_ascii=False, indent=2) + "\n")
    visual["figures"][0]["png_sha256"] = digest(final_png)
    write(case / "03-审查工作区/附图/visual-review.json", json.dumps(visual, ensure_ascii=False, indent=2) + "\n")
    forged = run(VERIFIER, "--brief", str(brief), "--case-dir", str(case), "--drawio-skill-dir", str(DRAWIO_SKILL), "--output", str(output))
    assert forged.returncode == 2
    forged_payload = json.loads(output.read_text(encoding="utf-8"))
    forged_codes = {item["code"] for item in forged_payload["errors"]}
    assert "DRAWING-EXPORT-STALE" not in forged_codes
    assert "DRAWING-VISUAL-STALE" not in forged_codes
    assert "DRAWING-EXPORT-REPRODUCE" in forged_codes


@pytest.mark.parametrize(
    ("constraint_id", "observable", "measurement", "negative_fixture"),
    [
        ("PATENT-DRAWING-SOURCE-BINDING", "source-binding-observable", "source-binding-pass", "stale-source.json"),
        ("PATENT-DRAWING-TECH-COVERAGE", "tech-coverage-observable", "tech-coverage-pass", "missing-element.json"),
        ("PATENT-DRAWING-DIRECT-CONNECTOR", "direct-connector-observable", "direct-connector-pass", "historical-text-waypoint.json"),
        ("PATENT-DRAWING-COLOR", "color-observable", "color-pass", "flashy-color.json"),
        ("PATENT-DRAWING-OFFICIAL-EXPORT", "official-export-observable", "official-export-pass", "forged-export.json"),
        ("PATENT-DRAWING-VISUAL-BINDING", "visual-binding-observable", "visual-binding-pass", "unapproved-visual.json"),
    ],
)
def test_stability_checker_has_positive_and_negative_evidence(constraint_id, observable, measurement, negative_fixture):
    positive = run(
        STABILITY_CHECKER,
        "--report", str(STABILITY_ASSETS / "positive-final-verification.json"),
        "--constraint", constraint_id,
        "--observable", observable,
        "--measurement", measurement,
    )
    assert positive.returncode == 0, positive.stdout + positive.stderr
    positive_payload = json.loads(positive.stdout.splitlines()[-1])
    assert positive_payload["passed_constraint_ids"] == [constraint_id]
    assert positive_payload["measurements"][constraint_id][measurement] is True

    negative = run(
        STABILITY_CHECKER,
        "--report", str(STABILITY_ASSETS / negative_fixture),
        "--constraint", constraint_id,
        "--observable", observable,
        "--measurement", measurement,
    )
    assert negative.returncode == 3, negative.stdout + negative.stderr
    negative_payload = json.loads(negative.stdout.splitlines()[-1])
    assert negative_payload["failed_constraint_ids"] == [constraint_id]
    assert negative_payload["measurements"][constraint_id][measurement] is False


def test_stability_contract_covers_all_hard_constraints():
    contract = json.loads((SKILL / "config/instruction-stability-contract.json").read_text(encoding="utf-8"))
    constraint_ids = {item["id"] for item in contract["constraints"] if item["severity"] == "hard"}
    assert constraint_ids == {
        "PATENT-DRAWING-SOURCE-BINDING",
        "PATENT-DRAWING-TECH-COVERAGE",
        "PATENT-DRAWING-DIRECT-CONNECTOR",
        "PATENT-DRAWING-COLOR",
        "PATENT-DRAWING-OFFICIAL-EXPORT",
        "PATENT-DRAWING-VISUAL-BINDING",
    }
    assert contract["stability"]["minimum_runs"] == 3

def test_skill_is_domain_adapter_for_drawio_skill():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for required in (
        'version: "2.0.0"', "drawio-skill", "cn-patent-drawing-brief/v2",
        "Draw.io Desktop CLI", "patent_restrained_color", "verify_patent_drawings.py",
    ):
        assert required in skill
    assert "不得改用 Pillow" in skill
    assert "from PIL" not in skill
