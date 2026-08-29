"""独立中国专利 Skill 包的轻量边界回归。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_boundary_verifier_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_package.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "PASS"


def test_no_business_slash_commands_or_mcp_server_are_bundled():
    assert not (ROOT / "commands").exists()
    assert not (ROOT / "mcp_server").exists()


def test_orchestrator_is_lightweight_and_routes_by_stage():
    text = (ROOT / "skills" / "cn-patent-workflow" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) < 100
    for skill in (
        "patent-application-creator-CN",
        "patent-reviewer-CN",
        "patent-claims-analyzer-CN",
        "patent-specification-reviewer-CN",
        "patent-formalities-reviewer-CN",
        "patent-diagram-generator-ZH",
    ):
        assert skill in text
    assert "不启动 MCP Server" in text
    assert "FAISS" in text


def test_legal_sources_have_topic_router():
    index_path = ROOT / "references" / "cn-legal-sources" / "source-index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["schema_id"] == "cn-patent-legal-source-index/v1"
    assert payload["policy"]["default"] == "load_topic_files_only"
    assert "claims_and_support" in payload["topics"]
    assert "subject_matter_and_computer_programs" in payload["topics"]
