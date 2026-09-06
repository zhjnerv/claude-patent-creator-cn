#!/usr/bin/env python3
"""独立复算 DOCX 组装报告的输入、输出哈希和证据新鲜度。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from typing import Any

SCHEMA_ID = "cn-patent-docx-assembly/v2"
RESULT_SCHEMA_ID = "cn-patent-docx-assembly-verification/v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("组装报告含 BOM")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("组装报告顶层必须是对象")
    return value



def check_docx_package(path: Path, errors: list[dict[str, str]]) -> None:
    """检查 Word 会在打开阶段强制修复的最小 OOXML 结构问题。"""
    try:
        with ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                errors.append({"code": "DOCX-PACKAGE-CRC", "message": f"DOCX ZIP 成员 CRC 损坏：{bad_member}"})
                return
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/_rels/document.xml.rels"}
            missing = sorted(required - set(archive.namelist()))
            if missing:
                errors.append({"code": "DOCX-PACKAGE-MISSING", "message": f"DOCX 缺少必需成员：{missing}"})
                return
            document_bytes = archive.read("word/document.xml")
    except BadZipFile:
        errors.append({"code": "DOCX-PACKAGE-ZIP", "message": "输出文件不是有效 DOCX ZIP 包"})
        return
    try:
        document_text = document_bytes.decode("utf-8")
        ET.fromstring(document_bytes)
    except (UnicodeDecodeError, ET.ParseError) as exc:
        errors.append({"code": "DOCX-PACKAGE-XML", "message": f"word/document.xml 不是有效 XML：{exc}"})
        return
    root_match = re.search(r"<w:document\b[^>]*>", document_text)
    if root_match is None:
        errors.append({"code": "DOCX-PACKAGE-ROOT", "message": "word/document.xml 缺少 w:document 根节点"})
        return
    root_tag = root_match.group(0)
    declared = set(re.findall(r"xmlns:([A-Za-z_][\w.-]*)=\"[^\"]+\"", root_tag))
    ignorable_match = re.search(r"mc:Ignorable=\"([^\"]*)\"", root_tag)
    ignored = set(ignorable_match.group(1).split()) if ignorable_match else set()
    missing_ignored = sorted(ignored - declared)
    if missing_ignored:
        errors.append({
            "code": "DOCX-PACKAGE-IGNORABLE-NS",
            "message": f"mc:Ignorable 引用了未声明的命名空间前缀：{missing_ignored}；Microsoft Word 会提示恢复文档",
        })

def verify(report_path: Path) -> dict[str, Any]:
    report = load_json(report_path)
    errors: list[dict[str, str]] = []

    def check_file(path_value: Any, expected: Any, artifact_id: str) -> None:
        if not isinstance(path_value, str) or not path_value:
            errors.append({"code": "DOCX-EVIDENCE-PATH", "message": f"{artifact_id} 缺少路径"})
            return
        path = Path(path_value).resolve()
        if not path.is_file():
            errors.append({"code": "DOCX-EVIDENCE-MISSING", "message": f"{artifact_id} 文件不存在：{path}"})
            return
        actual = sha256(path)
        if expected != actual:
            errors.append({"code": "DOCX-EVIDENCE-STALE", "message": f"{artifact_id} 哈希与当前文件不一致"})

    if report.get("schema") != SCHEMA_ID:
        errors.append({"code": "DOCX-EVIDENCE-SCHEMA", "message": f"schema 必须为 {SCHEMA_ID}"})
    if report.get("status") not in {"STRUCTURE_VERIFIED", "STRUCTURE_VERIFIED_VISUAL_REVIEW_PENDING"}:
        errors.append({"code": "DOCX-EVIDENCE-STATUS", "message": "组装报告状态无效"})
    check_file(report.get("output"), report.get("output_sha256"), "output_docx")
    output_value = report.get("output")
    if isinstance(output_value, str) and output_value and Path(output_value).resolve().is_file():
        check_docx_package(Path(output_value).resolve(), errors)
    inputs = report.get("inputs") or {}
    check_file(inputs.get("template"), inputs.get("template_sha256"), "template")
    artifacts = inputs.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append({"code": "DOCX-EVIDENCE-INPUTS", "message": "缺少逐文件 inputs.artifacts"})
        artifacts = []
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append({"code": "DOCX-EVIDENCE-INPUTS", "message": "inputs.artifacts 含非对象项"})
            continue
        artifact_id = item.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen:
            errors.append({"code": "DOCX-EVIDENCE-INPUTS", "message": f"artifact_id 缺失或重复：{artifact_id}"})
            continue
        seen.add(artifact_id)
        check_file(item.get("path"), item.get("sha256"), artifact_id)
    for required in {"claims", "specification", "abstract", "figure_index"}:
        if required not in seen:
            errors.append({"code": "DOCX-EVIDENCE-INPUTS", "message": f"缺少必需输入：{required}"})

    return {
        "schema_id": RESULT_SCHEMA_ID,
        "report": str(report_path),
        "report_sha256": sha256(report_path),
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "evidence_scope": {
            "proves": ["组装报告绑定的模板、源文件、图片和输出 DOCX 当前仍为同一字节版本"],
            "does_not_prove": ["DOCX 法律内容正确", "未执行的视觉复核已经完成"],
        },
    }


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.report.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {"schema_id": RESULT_SCHEMA_ID, "status": "FAIL", "errors": [{"code": "DOCX-EVIDENCE-INPUT", "message": str(exc)}]}
    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    if args.output:
        write_atomic(args.output.resolve(), payload)
    else:
        print(payload.decode("utf-8"), end="")
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
