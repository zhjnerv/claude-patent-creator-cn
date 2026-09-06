#!/usr/bin/env python3
"""把本仓库以 Codex 文件系统 Skill 集合一键安装到用户目录。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_NAME = "claude-patent-creator-cn"
REQUIRED_SKILLS = (
    "cn-patent-workflow",
    "cn-patent-application-creator",
    "cn-patent-claims-analyzer",
    "cn-patent-diagram-generator",
    "cn-patent-formalities-reviewer",
    "cn-patent-reviewer",
    "cn-patent-specification-reviewer",
)
RUNTIME_ENTRIES = (
    ".codex-plugin",
    "assets",
    "references",
    "scripts",
    "skills",
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "pyproject.toml",
)
IGNORE_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "archive",
    "dist",
    "build",
}


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def copy_runtime(source: Path, staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=False)
    for name in RUNTIME_ENTRIES:
        item = source / name
        if not item.exists():
            continue
        target = staging / name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                ignore=shutil.ignore_patterns(*IGNORE_NAMES, "*.pyc", "*.pyo"),
            )
        else:
            shutil.copy2(item, target)


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_dependencies(runtime: Path, *, with_dev: bool) -> dict[str, Any]:
    venv = runtime / ".venv"
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "创建虚拟环境失败；Debian/Ubuntu 请先安装 python3-venv，"
            "然后重新运行安装器。"
        ) from exc
    python = venv_python(venv)
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True, stdout=sys.stderr)
    extras = "docx,dev" if with_dev else "docx"
    subprocess.run(
        [str(python), "-m", "pip", "install", f".[{extras}]"],
        cwd=runtime,
        check=True,
        stdout=sys.stderr,
    )
    subprocess.run(
        [str(python), "scripts/verify_package.py"],
        cwd=runtime,
        check=True,
        stdout=sys.stderr,
    )
    return {
        "python": str(python),
        "extras": extras,
    }


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def install_skill_links(runtime: Path, skills_home: Path, *, force: bool) -> list[dict[str, str]]:
    skills_home.mkdir(parents=True, exist_ok=True)
    installed: list[dict[str, str]] = []
    for name in REQUIRED_SKILLS:
        source = runtime / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise RuntimeError(f"运行时缺少 Skill：{name}")
        target = skills_home / name
        if target.exists() or target.is_symlink():
            same_target = False
            if target.is_symlink():
                try:
                    same_target = target.resolve() == source.resolve()
                except OSError:
                    same_target = False
            if not same_target and not force:
                raise RuntimeError(f"Codex Skill 已存在，使用 --force 才能替换：{target}")
            remove_path(target)
        mode = "symlink"
        try:
            target.symlink_to(source, target_is_directory=True)
        except OSError:
            shutil.copytree(source, target)
            mode = "copy"
        installed.append({"name": name, "path": str(target), "mode": mode})
    return installed


def write_manifest(runtime: Path, codex_home: Path, installed: list[dict[str, str]], deps: dict[str, Any] | None) -> Path:
    manifest = {
        "schema_id": "cn-patent-codex-skill-install/v1",
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(runtime),
        "codex_home": str(codex_home),
        "entry_skill": "cn-patent-workflow",
        "skills": installed,
        "dependencies": deps,
        "invocation": "$cn-patent-workflow",
    }
    path = runtime / "codex-install.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1], help="仓库根目录")
    parser.add_argument("--codex-home", type=Path, default=default_codex_home(), help="Codex 用户目录")
    parser.add_argument("--skip-deps", action="store_true", help="不创建运行时虚拟环境")
    parser.add_argument("--with-dev", action="store_true", help="同时安装 pytest 等开发依赖")
    parser.add_argument("--force", action="store_true", help="替换已有同名 Skill 和运行时")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    codex_home = args.codex_home.expanduser().resolve()
    if not (source / ".codex-plugin" / "plugin.json").is_file():
        raise SystemExit(f"不是有效项目根目录：{source}")
    for name in REQUIRED_SKILLS:
        if not (source / "skills" / name / "SKILL.md").is_file():
            raise SystemExit(f"源仓库缺少 Skill：{name}")

    vendor = codex_home / "vendor"
    runtime = vendor / PLUGIN_NAME
    vendor.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{PLUGIN_NAME}-", dir=vendor) as temporary:
        staging = Path(temporary) / PLUGIN_NAME
        copy_runtime(source, staging)

        backup: Path | None = None
        if runtime.exists():
            if not args.force:
                raise SystemExit(f"运行时已存在，使用 --force 更新：{runtime}")
            backup = vendor / f".{PLUGIN_NAME}.backup"
            remove_path(backup)
            runtime.replace(backup)
        try:
            staging.replace(runtime)
            deps = None if args.skip_deps else install_dependencies(runtime, with_dev=args.with_dev)
            installed = install_skill_links(runtime, codex_home / "skills", force=args.force)
            manifest_path = write_manifest(runtime, codex_home, installed, deps)
        except Exception:
            remove_path(runtime)
            if backup is not None and backup.exists():
                backup.replace(runtime)
            raise
        else:
            if backup is not None:
                remove_path(backup)

    result = {
        "status": "PASS",
        "runtime_root": str(runtime),
        "entry_skill": "cn-patent-workflow",
        "invocation": "$cn-patent-workflow",
        "manifest": str(manifest_path),
        "skills": installed,
        "restart_required": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
