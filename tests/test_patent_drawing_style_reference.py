from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/cn-patent-diagram-generator"
ANALYZER = SKILL / "scripts/analyze_drawing_reference.py"
VALIDATOR = SKILL / "scripts/validate_drawing_style_brief.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_drawio(path: Path, *, changed_ids: bool, absolute_edge: bool) -> None:
    a = "new-a" if changed_ids else "A"
    b = "new-b" if changed_ids else "B"
    source = f' source="{a}"' if not absolute_edge else f' source="{a}"'
    target = f' target="{b}"' if not absolute_edge else ""
    target_point = '<mxPoint x="350" y="420" as="targetPoint"/>' if absolute_edge else ""
    path.write_text(
        f'''<mxfile compressed="false"><diagram name="Page-1"><mxGraphModel pageWidth="827" pageHeight="1169" gridSize="10"><root>
        <mxCell id="0"/><mxCell id="1" parent="0"/>
        <mxCell id="{a}" value="100 主模块" style="rounded=1;whiteSpace=wrap;html=1;fontSize={'24' if changed_ids else '16'};fontFamily=Times New Roman;fillColor=#EAF2F8;strokeColor=#405F73;" vertex="1" parent="1"><mxGeometry x="100" y="100" width="300" height="100" as="geometry"/></mxCell>
        <mxCell id="{b}" value="110 支撑模块" style="rounded=1;whiteSpace=wrap;html=1;fontSize={'24' if changed_ids else '16'};fontFamily=Times New Roman;fillColor=#EEF4EA;strokeColor=#52634E;" vertex="1" parent="1"><mxGeometry x="{'450' if changed_ids else '100'}" y="300" width="300" height="100" as="geometry"/></mxCell>
        <mxCell id="R1" value="传递" edge="1" parent="1"{source}{target} style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=block;strokeWidth=1.4;"><mxGeometry relative="1" as="geometry">{target_point}</mxGeometry></mxCell>
        </root></mxGraphModel></diagram></mxfile>''',
        encoding="utf-8",
    )


def run(script: Path, *args: str):
    return subprocess.run([sys.executable, str(script), *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)


def test_reference_analyzer_separates_visual_intent_and_absolute_endpoint(tmp_path):
    baseline = tmp_path / "baseline.drawio"
    reference = tmp_path / "reference.drawio"
    output = tmp_path / "style-brief.json"
    write_drawio(baseline, changed_ids=False, absolute_edge=False)
    write_drawio(reference, changed_ids=True, absolute_edge=True)
    result = run(
        ANALYZER,
        "--baseline", str(baseline), "--reference", str(reference),
        "--case-dir", str(tmp_path), "--case-id", "case", "--output", str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["analysis_status"] == "REVIEW_REQUIRED"
    assert len(payload["matching"]["matched_nodes"]) == 2
    assert {item["method"] for item in payload["matching"]["matched_nodes"]} == {"reference_sign"}
    assert payload["reusable_style"]["typography"]["font_size"] == 24.0
    assert "STYLE-REFERENCE-ABSOLUTE-ENDPOINT" in {item["code"] for item in payload["structural_anomalies"]}
    assert payload["approval"]["status"] == "pending"

    approved = run(
        ANALYZER,
        "--baseline", str(baseline), "--reference", str(reference),
        "--case-dir", str(tmp_path), "--case-id", "case", "--output", str(output),
        "--approve-by", "用户",
    )
    assert approved.returncode == 0
    validation = run(VALIDATOR, "--style-brief", str(output), "--case-dir", str(tmp_path))
    assert validation.returncode == 0, validation.stdout + validation.stderr
    report = json.loads(validation.stdout)
    assert report["status"] == "PASS"
    assert report["style_brief_sha256"] == digest(output)


def test_style_brief_stale_reference_is_blocked(tmp_path):
    baseline = tmp_path / "baseline.drawio"
    reference = tmp_path / "reference.drawio"
    output = tmp_path / "style-brief.json"
    write_drawio(baseline, changed_ids=False, absolute_edge=False)
    write_drawio(reference, changed_ids=False, absolute_edge=False)
    assert run(
        ANALYZER, "--baseline", str(baseline), "--reference", str(reference),
        "--case-dir", str(tmp_path), "--case-id", "case", "--output", str(output), "--approve-by", "用户",
    ).returncode == 0
    reference.write_text(reference.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    validation = run(VALIDATOR, "--style-brief", str(output), "--case-dir", str(tmp_path))
    assert validation.returncode == 2
    assert "STYLE-BRIEF-STALE" in validation.stdout
