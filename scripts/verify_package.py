#!/usr/bin/env python3
"""验证中国专利 Skill 包的独立性、资源完整性和轻量边界。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = {
    "cn-patent-workflow",
    "patent-application-creator-CN",
    "patent-reviewer-CN",
    "patent-claims-analyzer-CN",
    "patent-specification-reviewer-CN",
    "patent-formalities-reviewer-CN",
    "patent-diagram-generator-ZH",
}
FORBIDDEN_TOP_LEVEL = {"mcp_server", "commands"}
FORBIDDEN_DEPENDENCIES = {
    "torch",
    "sentence-transformers",
    "faiss-cpu",
    "rank-bm25",
    "google-cloud-bigquery",
    "mcp",
}


def main() -> int:
    errors: list[str] = []

    for name in sorted(REQUIRED_SKILLS):
        if not (ROOT / "skills" / name / "SKILL.md").is_file():
            errors.append(f"缺少 Skill：{name}")

    for name in sorted(FORBIDDEN_TOP_LEVEL):
        if (ROOT / name).exists():
            errors.append(f"存在禁止的重型目录：{name}")

    legal_root = ROOT / "references" / "cn-legal-sources"
    for relative in (
        "专利法(2020-10-17).md",
        "专利法实施细则(2023-12-21).md",
        "审查指南2026MD/guide-full.md",
        "source-index.json",
    ):
        path = legal_root / relative
        if not path.is_file() or not path.read_bytes():
            errors.append(f"法源缺失或为空：{relative}")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for dependency in sorted(FORBIDDEN_DEPENDENCIES):
        if f'"{dependency}' in pyproject:
            errors.append(f"不应引入主项目重型依赖：{dependency}")

    for path in ROOT.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            errors.append(f"存在缓存产物：{path.relative_to(ROOT)}")
            continue
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"文件含 UTF-8 BOM：{path.relative_to(ROOT)}")
        if path.suffix == ".json":
            try:
                json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"JSON 无效：{path.relative_to(ROOT)}：{exc}")
        if path.suffix in {".py", ".md"} and path.resolve() != Path(__file__).resolve():
            text = raw.decode("utf-8", errors="replace")
            if "from mcp_server" in text or "import mcp_server" in text:
                errors.append(f"存在对主项目 mcp_server 的反向依赖：{path.relative_to(ROOT)}")

    report = {
        "schema_id": "cn-patent-skill-package-verification/v1",
        "status": "PASS" if not errors else "FAIL",
        "required_skills": sorted(REQUIRED_SKILLS),
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
