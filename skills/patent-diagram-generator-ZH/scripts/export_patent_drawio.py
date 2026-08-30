#!/usr/bin/env python3
"""使用 Draw.io Desktop CLI 导出中国专利附图，并写入 DPI 与证据报告。"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_drawio() -> str:
    for name in ("drawio", "draw.io"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        Path("/Applications/draw.io.app/Contents/MacOS/draw.io"),
        Path(r"C:\Program Files\draw.io\draw.io.exe"),
        Path(os.environ.get("LOCALAPPDATA", ""), r"Programs\draw.io\draw.io.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError("未找到 Draw.io Desktop CLI（drawio/draw.io）")


def cli_version(binary: str) -> str:
    result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20, check=False)
    value = (result.stdout or result.stderr).strip().splitlines()
    return value[-1] if value else "unknown"


def run_export(binary: str, source: Path, output: Path, fmt: str, width: int, border: int) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patent_drawio_export_") as raw:
        temp = Path(raw) / f"export.{fmt}"
        command = [
            binary, "-x", "-f", fmt, "--size", "page", "--theme", "light",
            "--border", str(border), "-o", str(temp),
        ]
        if os.name == "nt":
            # Windows 无头/远端会话下 Electron 需要软件渲染，否则 GPU 进程崩溃导致导出失败
            command.extend(["--no-sandbox", "--disable-gpu", "--use-gl=swiftshader"])
        if fmt in {"png", "jpg", "svg"}:
            command.extend(["--width", str(width)])
        command.append(str(source))
        attempts = [command]
        if sys.platform.startswith("linux") and shutil.which("xvfb-run"):
            attempts.insert(0, [shutil.which("xvfb-run") or "xvfb-run", "-a", *command])
        messages: list[str] = []
        for attempt in attempts:
            result = subprocess.run(attempt, capture_output=True, text=True, timeout=120, check=False)
            messages.append((result.stdout or "") + (result.stderr or ""))
            if result.returncode == 0 and temp.is_file() and temp.stat().st_size > 0:
                shutil.copy2(temp, output)
                return attempt
        raise RuntimeError("Draw.io CLI 导出失败：" + " | ".join(message.strip()[-500:] for message in messages))


def png_chunks(data: bytes):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("输出不是有效 PNG")
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = data[offset + 8 + length:offset + 12 + length]
        yield kind, payload, crc
        offset += 12 + length


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def set_png_dpi(path: Path, dpi: float) -> None:
    data = path.read_bytes()
    ppm = round(dpi / 0.0254)
    phys = struct.pack(">IIB", ppm, ppm, 1)
    parts = [PNG_SIGNATURE]
    inserted = False
    for kind, payload, _crc in png_chunks(data):
        if kind == b"pHYs":
            if not inserted:
                parts.append(chunk(b"pHYs", phys))
                inserted = True
            continue
        parts.append(chunk(kind, payload))
        if kind == b"IHDR" and not inserted:
            parts.append(chunk(b"pHYs", phys))
            inserted = True
    path.write_bytes(b"".join(parts))


def inspect_png(path: Path) -> dict[str, Any]:
    width = height = None
    dpi = None
    for kind, payload, _crc in png_chunks(path.read_bytes()):
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"pHYs" and len(payload) == 9:
            xppm, yppm, unit = struct.unpack(">IIB", payload)
            if unit == 1:
                dpi = [round(xppm * 0.0254, 4), round(yppm * 0.0254, 4)]
    return {"width": width, "height": height, "dpi": dpi, "bytes": path.stat().st_size, "sha256": sha256(path)}


def drawio_page_width(path: Path) -> int:
    root = ET.parse(path).getroot()
    model = root.find("./diagram/mxGraphModel") if root.tag == "mxfile" else root
    if model is None:
        raise ValueError("drawio 缺少 mxGraphModel")
    try:
        return int(float(model.get("pageWidth", "0")))
    except ValueError as exc:
        raise ValueError("drawio pageWidth 无效") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 Draw.io Desktop 官方引擎导出专利附图")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--png", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--svg", type=Path)
    parser.add_argument("--width", type=int, help="最终像素宽度；省略时按 drawio pageWidth × DPI/96 计算")
    parser.add_argument("--dpi", type=float, default=300.0)
    parser.add_argument("--border", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        source = args.input.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        binary = find_drawio()
        version = cli_version(binary)
        width = args.width or round(drawio_page_width(source) * args.dpi / 96.0)
        if width <= 0:
            raise ValueError("导出宽度必须大于 0")
        png_command = run_export(binary, source, args.png.resolve(), "png", width, args.border)
        set_png_dpi(args.png.resolve(), args.dpi)
        outputs: dict[str, Any] = {"png": {"path": str(args.png.resolve()), **inspect_png(args.png.resolve())}}
        commands = {"png": png_command}
        if args.svg:
            svg_command = run_export(binary, source, args.svg.resolve(), "svg", width, args.border)
            outputs["svg"] = {"path": str(args.svg.resolve()), "bytes": args.svg.stat().st_size, "sha256": sha256(args.svg.resolve())}
            commands["svg"] = svg_command
        report = {
            "schema_id": "cn-patent-drawio-export/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "renderer": {"kind": "drawio_desktop_cli", "binary": binary, "version": version},
            "source": {"path": str(source), "sha256": sha256(source)},
            "parameters": {"width": width, "dpi": args.dpi, "border": args.border, "size": "page", "theme": "light"},
            "commands": commands,
            "outputs": outputs,
            "status": "PASS",
        }
    except Exception as exc:
        report = {"schema_id": "cn-patent-drawio-export/v1", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
