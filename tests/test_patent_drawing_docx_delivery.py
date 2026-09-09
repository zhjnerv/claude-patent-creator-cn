from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/cn-patent-diagram-generator/scripts/verify_drawing_docx_delivery.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture(tmp_path: Path):
    png = tmp_path / "drawings/图1.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"current-png")
    brief = tmp_path / "drawing-brief.json"
    write_json(brief, {"figures": [{"figure_number": 1, "outputs": {"final_png": "drawings/图1.png"}}]})
    drawing = tmp_path / "drawing-verification.json"
    write_json(drawing, {"status": "PASS", "errors": [], "brief_sha256": digest(brief)})
    docx = tmp_path / "output.docx"
    docx.write_bytes(b"docx")
    report = tmp_path / "docx-report.json"
    write_json(report, {
        "status": "STRUCTURE_VERIFIED", "output": str(docx), "output_sha256": digest(docx),
        "inputs": {"artifacts": [{"artifact_id": "figure_1", "path": str(png), "sha256": digest(png)}]},
        "render": {"requested": False},
    })
    verification = tmp_path / "docx-verification.json"
    write_json(verification, {"status": "PASS", "errors": []})
    return brief, drawing, report, verification, png


def run(tmp_path: Path, brief: Path, drawing: Path, report: Path, verification: Path):
    output = tmp_path / "delivery.json"
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--case-dir", str(tmp_path), "--brief", str(brief),
        "--drawing-verification", str(drawing), "--docx-report", str(report),
        "--docx-verification", str(verification), "--output", str(output),
    ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False)
    return result, json.loads(output.read_text(encoding="utf-8"))


def test_drawing_docx_delivery_passes_for_current_png(tmp_path):
    brief, drawing, report, verification, _png = fixture(tmp_path)
    result, payload = run(tmp_path, brief, drawing, report, verification)
    assert result.returncode == 0, result.stdout + result.stderr
    assert payload["status"] == "PASS"
    assert payload["figure_count"] == 1


def test_drawing_docx_delivery_blocks_stale_embedded_png(tmp_path):
    brief, drawing, report, verification, png = fixture(tmp_path)
    png.write_bytes(b"changed")
    result, payload = run(tmp_path, brief, drawing, report, verification)
    assert result.returncode == 2
    assert "DELIVERY-DOCX-FIGURE-STALE" in {item["code"] for item in payload["errors"]}
