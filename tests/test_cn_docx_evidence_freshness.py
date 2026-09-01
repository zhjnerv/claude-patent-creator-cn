"""DOCX 组装证据的新鲜度回归，不依赖 Word。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/patent-application-creator-CN/scripts/verify_docx_assembly.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_docx_assembly", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_docx_report_binds_every_source_and_detects_stale_input(tmp_path):
    module = load_module()
    template = tmp_path / "template.docx"
    output = tmp_path / "output.docx"
    artifacts = []
    for artifact_id, name in [("claims", "权利要求书.md"), ("specification", "说明书.md"), ("abstract", "说明书摘要.md"), ("figure_index", "说明书附图.md"), ("figure_1", "图1.png")]:
        path = tmp_path / name
        path.write_bytes(artifact_id.encode("utf-8"))
        artifacts.append({"artifact_id": artifact_id, "path": str(path), "sha256": digest(path)})
    template.write_bytes(b"template")
    output.write_bytes(b"docx")
    report_path = tmp_path / "docx-assembly-report.json"
    report_path.write_text(json.dumps({
        "schema": "cn-patent-docx-assembly/v2", "status": "STRUCTURE_VERIFIED",
        "output": str(output), "output_sha256": digest(output),
        "inputs": {"template": str(template), "template_sha256": digest(template), "source_dir": str(tmp_path), "artifacts": artifacts},
    }, ensure_ascii=False), encoding="utf-8")
    assert module.verify(report_path)["status"] == "PASS"
    (tmp_path / "说明书.md").write_text("changed", encoding="utf-8")
    stale = module.verify(report_path)
    assert stale["status"] == "FAIL"
    assert any(item["code"] == "DOCX-EVIDENCE-STALE" for item in stale["errors"])
