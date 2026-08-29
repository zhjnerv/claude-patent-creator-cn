#!/usr/bin/env python3
"""按技术相关性与 IPC 相似度选择中国专利撰写范本。

候选 IPC 的获取顺序固定为：EPO OPS → 分类缓存 → 候选输入。EPO 没有凭据、
未收录或暂时失败时允许降级，但必须在报告中保留尝试状态和来源；无法取得 IPC
的候选不得成为机器推荐或最终选择。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_ID = "cn-patent-template-selection/v1"
SEARCH_SCHEMA_ID = "cn-patent-template-search/v1"
CANDIDATE_SCHEMA_ID = "cn-patent-template-candidates/v1"
IPC_RE = re.compile(r"^[A-H][0-9]{2}[A-Z](?:[0-9]+(?:/[0-9]+)?)?$")
IPC_EXTRACT_RE = re.compile(r"([A-H][0-9]{2}[A-Z](?:\s*[0-9]+(?:\s*/\s*[0-9]+)?)?)", re.IGNORECASE)


class SelectionError(ValueError):
    """范本候选或 IPC 选择合同无效。"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise SelectionError(f"{label}不存在：{path}") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise SelectionError(f"{label}含 BOM，必须使用 UTF-8 无 BOM")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SelectionError(f"{label}不是有效 UTF-8 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise SelectionError(f"{label}顶层必须是对象")
    return value


def normalize_ipc(code: str) -> str:
    if not isinstance(code, str):
        raise SelectionError("IPC 分类号必须是字符串")
    value = re.sub(r"\([^)]*\)", "", code.upper())
    match = IPC_EXTRACT_RE.search(value)
    if not match:
        raise SelectionError(f"无效 IPC 分类号：{code}")
    value = re.sub(r"\s+", "", match.group(1))
    if not IPC_RE.fullmatch(value):
        raise SelectionError(f"无效 IPC 分类号：{code}")
    return value


def normalize_ipc_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise SelectionError(f"{field}必须是数组")
    result: list[str] = []
    for item in value:
        code = normalize_ipc(item)
        if code not in result:
            result.append(code)
    return result


def ipc_parts(code: str) -> dict[str, str]:
    code = normalize_ipc(code)
    subclass = code[:4]
    remainder = code[4:]
    main_group = remainder.split("/", 1)[0] if remainder else ""
    return {
        "section": code[:1],
        "class": code[:3],
        "subclass": subclass,
        "main_group": f"{subclass}{main_group}" if main_group else subclass,
        "full": code,
    }


def compare_ipc(target: str, candidate: str) -> tuple[float, str]:
    left, right = ipc_parts(target), ipc_parts(candidate)
    if left["full"] == right["full"]:
        return 1.0, "exact"
    if left["main_group"] == right["main_group"] and left["main_group"] != left["subclass"]:
        return 0.85, "same_main_group"
    if left["subclass"] == right["subclass"]:
        return 0.65, "same_subclass"
    if left["class"] == right["class"]:
        return 0.45, "same_class"
    if left["section"] == right["section"]:
        return 0.20, "same_section"
    return 0.0, "none"


def best_ipc_match(target_codes: list[str], candidate_codes: list[str]) -> dict[str, Any]:
    best = {"score": 0.0, "level": "none", "target_ipc": None, "candidate_ipc": None}
    for target in target_codes:
        for candidate in candidate_codes:
            score, level = compare_ipc(target, candidate)
            if score > best["score"]:
                best = {
                    "score": score,
                    "level": level,
                    "target_ipc": target,
                    "candidate_ipc": candidate,
                }
    return best


def load_cache(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json(path, "分类缓存")
    records = payload.get("patents", payload)
    if not isinstance(records, dict):
        raise SelectionError("分类缓存必须是以公开号为键的对象，或包含 patents 对象")
    return records


def build_epo_resolver(command: str | None = None) -> Callable[[str], tuple[list[str], dict[str, Any]]]:
    """构造独立 EPO provider 调用器，避免反向依赖主项目。

    provider 通过 argv 最后一项接收公开号，并在 stdout 输出 JSON 对象：
    ``{"ipc_codes": ["G06F11/36"]}``。调用不经过 shell。
    """

    raw_command = (command or os.getenv("CN_PATENT_EPO_PROVIDER_COMMAND") or "").strip()

    def resolve(publication_number: str) -> tuple[list[str], dict[str, Any]]:
        attempt: dict[str, Any] = {"provider": "epo_ops", "status": "unavailable"}
        if not raw_command:
            attempt["reason"] = "未配置 CN_PATENT_EPO_PROVIDER_COMMAND"
            return [], attempt
        try:
            argv = shlex.split(raw_command)
        except ValueError as exc:
            attempt.update(status="error", reason=f"provider 命令解析失败：{exc}")
            return [], attempt
        if not argv:
            attempt["reason"] = "EPO provider 命令为空"
            return [], attempt
        try:
            completed = subprocess.run(
                [*argv, publication_number],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                timeout=60,
                check=False,
                shell=False,
            )
            if completed.returncode != 0:
                attempt.update(
                    status="error",
                    reason=f"provider 退出码 {completed.returncode}: {completed.stderr.strip()[-500:]}",
                )
                return [], attempt
            payload = json.loads(completed.stdout)
            if not isinstance(payload, dict):
                raise ValueError("provider 输出顶层必须是 JSON 对象")
            if payload.get("error"):
                attempt.update(status="error", reason=str(payload["error"]))
                return [], attempt
            codes = normalize_ipc_list(payload.get("ipc_codes", []), "EPO provider ipc_codes")
            if not codes:
                attempt.update(status="not_found", reason="EPO provider 未返回 IPC")
                return [], attempt
            attempt.update(status="success", ipc_codes=codes)
            return codes, attempt
        except Exception as exc:  # 外部 provider 失败必须进入报告，不得伪装成无分类。
            attempt.update(status="error", reason=f"{type(exc).__name__}: {exc}")
            return [], attempt

    return resolve


def epo_resolver(publication_number: str) -> tuple[list[str], dict[str, Any]]:
    """使用环境变量配置的独立 provider，保留旧的可注入 resolver 接口。"""

    return build_epo_resolver()(publication_number)


def resolve_candidate_ipc(
    candidate: dict[str, Any],
    cache: dict[str, dict[str, Any]],
    resolver: Callable[[str], tuple[list[str], dict[str, Any]]] = epo_resolver,
) -> tuple[list[str], str, list[dict[str, Any]]]:
    number = candidate["publication_number"]
    attempts: list[dict[str, Any]] = []
    codes, attempt = resolver(number)
    attempts.append(attempt)
    if codes:
        return codes, "epo_ops", attempts

    cached = cache.get(number)
    if isinstance(cached, dict) and cached.get("ipc_codes"):
        codes = normalize_ipc_list(cached["ipc_codes"], f"classification_cache.{number}.ipc_codes")
        source = str(cached.get("source") or "classification_cache")
        attempts.append({"provider": "classification_cache", "status": "success", "source": source})
        return codes, source, attempts

    if candidate.get("ipc_codes"):
        codes = normalize_ipc_list(candidate["ipc_codes"], f"{number}.ipc_codes")
        source = str(candidate.get("classification_source") or "candidate_input")
        attempts.append({"provider": "candidate_input", "status": "success", "source": source})
        return codes, source, attempts

    attempts.append({"provider": "candidate_input", "status": "not_found"})
    return [], "unresolved", attempts


def candidate_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values = payload.get("candidates", payload.get("shortlist"))
    if not isinstance(values, list) or not values:
        raise SelectionError("候选清单必须包含非空 candidates 数组")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            raise SelectionError(f"第 {index} 个候选不是对象")
        number = item.get("publication_number")
        title = item.get("title")
        score = item.get("technical_relevance_score")
        reason = item.get("technical_relevance_reason")
        if not isinstance(number, str) or not number.strip():
            raise SelectionError(f"第 {index} 个候选缺少 publication_number")
        number = number.replace(" ", "").upper()
        if number in seen:
            raise SelectionError(f"候选公开号重复：{number}")
        seen.add(number)
        if not isinstance(title, str) or not title.strip():
            raise SelectionError(f"{number} 缺少 title")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= float(score) <= 1:
            raise SelectionError(f"{number} 的 technical_relevance_score 必须在 0—1")
        if not isinstance(reason, str) or not reason.strip():
            raise SelectionError(f"{number} 缺少 technical_relevance_reason")
        normalized = dict(item)
        normalized["publication_number"] = number
        normalized["title"] = title.strip()
        normalized["technical_relevance_score"] = round(float(score), 6)
        normalized["technical_relevance_reason"] = reason.strip()
        result.append(normalized)
    return result


def rank_templates(
    search_manifest: dict[str, Any],
    candidates_payload: dict[str, Any],
    *,
    ipc_weight: float = 0.35,
    cache: dict[str, dict[str, Any]] | None = None,
    resolver: Callable[[str], tuple[list[str], dict[str, Any]]] = epo_resolver,
    selected_number: str | None = None,
    selection_reason: str | None = None,
) -> dict[str, Any]:
    if search_manifest.get("schema_id") != SEARCH_SCHEMA_ID:
        raise SelectionError(f"search-query.json 的 schema_id 必须是 {SEARCH_SCHEMA_ID}")
    target = search_manifest.get("target_ipc")
    if not isinstance(target, dict) or target.get("status") != "determined":
        raise SelectionError("目标 IPC 尚未确定；先在 technical-features.json 明确 ipc_codes 并重新生成 search-query.json")
    target_codes = normalize_ipc_list(target.get("ipc_codes"), "target_ipc.ipc_codes")
    if not target_codes:
        raise SelectionError("目标 IPC 为空，禁止进入范本选择")
    if not isinstance(ipc_weight, (int, float)) or isinstance(ipc_weight, bool) or not 0 < ipc_weight < 1:
        raise SelectionError("ipc_weight 必须大于 0 且小于 1")
    technical_weight = 1.0 - float(ipc_weight)
    ranked: list[dict[str, Any]] = []
    for candidate in candidate_list(candidates_payload):
        codes, source, attempts = resolve_candidate_ipc(candidate, cache or {}, resolver)
        match = best_ipc_match(target_codes, codes) if codes else {
            "score": 0.0, "level": "unresolved", "target_ipc": None, "candidate_ipc": None
        }
        technical_score = candidate["technical_relevance_score"]
        weighted = technical_weight * technical_score + float(ipc_weight) * float(match["score"])
        ranked.append({
            **candidate,
            "ipc_codes": codes,
            "ipc_status": "resolved" if codes else "unresolved",
            "classification_source": source,
            "classification_attempts": attempts,
            "ipc_similarity": match,
            "weighted_score": round(weighted, 6),
            "eligible": bool(codes),
        })
    ranked.sort(
        key=lambda item: (
            item["eligible"], item["weighted_score"], item["ipc_similarity"]["score"],
            item["technical_relevance_score"], item["publication_number"]
        ), reverse=True
    )
    eligible = [item for item in ranked if item["eligible"]]
    if not eligible:
        raise SelectionError("所有范本候选的 IPC 均未取得；不得在没有候选 IPC 的情况下选定范本")
    recommended = eligible[0]
    selected = recommended
    override = False
    if selected_number:
        number = selected_number.replace(" ", "").upper()
        selected = next((item for item in eligible if item["publication_number"] == number), None)
        if selected is None:
            raise SelectionError(f"指定范本 {number} 不存在或 IPC 未解析")
        override = number != recommended["publication_number"]
        if override and (not isinstance(selection_reason, str) or not selection_reason.strip()):
            raise SelectionError("人工选择未采用加权最高候选时，必须提供 --selection-reason")
    reason = (selection_reason or (
        "技术相关性与 IPC 相似度加权得分最高；IPC 相似度已作为独立权重进入选择。"
    )).strip()
    return {
        "schema_id": SCHEMA_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_ipc": {"status": "determined", "ipc_codes": target_codes, "source": target.get("source", "search-query.json")},
        "weights": {"technical_relevance": round(technical_weight, 6), "ipc_similarity": round(float(ipc_weight), 6)},
        "classification_policy": {
            "preferred_provider": "epo_ops",
            "fallback_order": ["classification_cache", "candidate_input"],
            "boundary": "EPO OPS 未配置、未收录或失败时允许使用有来源记录的缓存/输入分类；未取得 IPC 的候选不得入选。",
        },
        "candidates": ranked,
        "recommended": {
            "publication_number": recommended["publication_number"],
            "weighted_score": recommended["weighted_score"],
        },
        "selected": {
            "publication_number": selected["publication_number"],
            "weighted_score": selected["weighted_score"],
            "ipc_codes": selected["ipc_codes"],
            "ipc_similarity": selected["ipc_similarity"],
            "classification_source": selected["classification_source"],
            "override_recommended": override,
            "selection_reason": reason,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按技术相关性与 IPC 相似度加权选择中国专利范本")
    parser.add_argument("--search-query", required=True, type=Path, help="generate_search_query.py 输出")
    parser.add_argument("--candidates", required=True, type=Path, help="cn-patent-template-candidates/v1 候选清单")
    parser.add_argument("--output", required=True, type=Path, help="template-selection.json")
    parser.add_argument("--ipc-weight", type=float, default=0.35, help="IPC 相似度权重，默认 0.35")
    parser.add_argument("--classification-cache", type=Path, help="可选的公开号→IPC 分类缓存")
    parser.add_argument(
        "--epo-provider-command",
        default=os.getenv("CN_PATENT_EPO_PROVIDER_COMMAND"),
        help="可选 EPO provider 命令；程序会把公开号作为最后一个 argv 传入并读取 JSON stdout",
    )
    parser.add_argument("--selected", help="人工最终选定的公开号；省略时采用加权最高候选")
    parser.add_argument("--selection-reason", help="人工偏离推荐候选时的理由")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        search_manifest = load_json(args.search_query, "search-query.json")
        candidates_payload = load_json(args.candidates, "范本候选清单")
        if candidates_payload.get("schema_id") not in {None, CANDIDATE_SCHEMA_ID}:
            raise SelectionError(f"候选清单 schema_id 必须是 {CANDIDATE_SCHEMA_ID}")
        payload = rank_templates(
            search_manifest,
            candidates_payload,
            ipc_weight=args.ipc_weight,
            cache=load_cache(args.classification_cache),
            resolver=build_epo_resolver(args.epo_provider_command),
            selected_number=args.selected,
            selection_reason=args.selection_reason,
        )
        payload["inputs"] = {
            "search_query_path": str(args.search_query.resolve()),
            "search_query_sha256": sha256(args.search_query),
            "candidate_manifest_path": str(args.candidates.resolve()),
            "candidate_manifest_sha256": sha256(args.candidates),
        }
    except SelectionError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selected = payload["selected"]
    print(f"[OK] 范本 IPC 加权选择报告：{args.output}")
    print(
        f"[INFO] 选定 {selected['publication_number']}；"
        f"IPC 相似度 {selected['ipc_similarity']['score']:.2f}；"
        f"综合得分 {selected['weighted_score']:.3f}；来源 {selected['classification_source']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
