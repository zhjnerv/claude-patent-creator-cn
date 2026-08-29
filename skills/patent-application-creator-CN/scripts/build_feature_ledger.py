#!/usr/bin/env python3
"""区别特征表：技术特征在权利要求、说明书与附图之间的四向对账。

问题背景：权利要求、说明书和附图各自持有一份技术事实副本，彼此只靠散文
连接。范本学习、检索边界和起草三段各自记一套特征编号，谁也对不上谁。本
脚本把全案技术特征收敛为唯一台账（cn-patent-feature-ledger/v1），并做四向
对账：

  台账 -> 权利要求   登记的落点在权利要求原文中确实存在
  权利要求 -> 台账   权利要求实际出现的项号都被登记过
  台账 -> 说明书     每个特征在说明书有可检索到的落点
  台账 -> 附图       component 标记进附图标记清单、step 标记不进；
                     附图标记清单与台账互为全集

脚本只做可复算的文本定位与集合运算。命中不等于得到支持，未命中也不等于
缺乏支持——法律判断由 REVIEW_REQUIRED 承载，不由本脚本给出。

退出码：0 工具成功执行；2 存在 DETERMINISTIC_FAIL；3 输入/路径/编码/JSON 无效。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

SCHEMA_ID = "cn-patent-feature-ledger/v1"
REPORT_SCHEMA_ID = "cn-patent-feature-ledger-report/v1"
LEGAL_EFFECT = "ADVISORY_ONLY"

EXIT_OK = 0
EXIT_DETERMINISTIC_FAIL = 2
EXIT_INPUT_ERROR = 3

FEATURE_ID_RE = re.compile(r"^F\d{3}$")
CLAIM_HEAD_RE = re.compile(r"^\s*(\d+)\s*[.、．]\s*(.+)$")
REFERENCE_LIST_RE = re.compile(r"图\s*中\s*[：:](.+?)。", re.S)
REFERENCE_ITEM_RE = re.compile(r"(\d+)\s*[-−–]\s*([^、。]+)")
SECTION_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(技术领域|背景技术|发明内容|附图说明|具体实施方式)\s*$",
    re.MULTILINE,
)

CLASSIFICATION_LABEL = {
    "preamble": "前序（共有）",
    "distinguishing": "区别特征",
    "fallback_only": "仅说明书（33条弹药）",
}
PRIOR_ART_LABEL = {
    "disclosed": "已被公开",
    "partially_disclosed": "部分公开",
    "not_found_in_searched_outlets": "已检索出口未发现",
    "not_searched": "未检索",
}


class LedgerError(ValueError):
    """输入不符合 v1 台账合同时抛出。"""


def normalize(text: str) -> str:
    """NFKC 归一并压掉全部空白，避免全半角与换行造成的假阴性。"""

    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def read_text(path: Path, label: str) -> str:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LedgerError(f"{label}文件不存在：{path}") from exc
    except OSError as exc:
        raise LedgerError(f"{label}文件不可读：{path}（{exc}）") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise LedgerError(f"{label}含 BOM，必须使用 UTF-8 无 BOM：{path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LedgerError(f"{label}不是有效 UTF-8：{path}") from exc


def load_ledger(path: Path) -> dict[str, Any]:
    text = read_text(path, "区别特征表")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LedgerError(f"区别特征表 JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise LedgerError("区别特征表必须是对象")
    if data.get("schema_id") != SCHEMA_ID:
        raise LedgerError(f"schema_id 必须是 {SCHEMA_ID}")
    features = data.get("features")
    if not isinstance(features, list) or not features:
        raise LedgerError("features 必须是非空数组")

    seen: set[str] = set()
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise LedgerError(f"第 {index} 个特征必须是对象")
        fid = feature.get("feature_id")
        if not isinstance(fid, str) or not FEATURE_ID_RE.match(fid):
            raise LedgerError(f"第 {index} 个特征的 feature_id 必须形如 F001")
        if fid in seen:
            raise LedgerError(f"特征编号重复：{fid}")
        seen.add(fid)
        for field in ("name", "statement", "classification"):
            if not isinstance(feature.get(field), str) or not feature[field].strip():
                raise LedgerError(f"特征 {fid} 的 {field} 必须是非空字符串")
        if feature["classification"] not in CLASSIFICATION_LABEL:
            raise LedgerError(f"特征 {fid} 的 classification 非法：{feature['classification']}")
        if not isinstance(feature.get("evidence"), list) or not feature["evidence"]:
            raise LedgerError(f"特征 {fid} 必须提供至少一条实现证据 evidence")
        if not isinstance(feature.get("spec_sites"), list) or not feature["spec_sites"]:
            raise LedgerError(f"特征 {fid} 必须提供至少一个说明书落点 spec_sites")
        for key in ("claim_sites", "drawing_sites"):
            if key in feature and not isinstance(feature[key], list):
                raise LedgerError(f"特征 {fid} 的 {key} 必须是数组")
    return data


def parse_claims(text: str) -> dict[int, str]:
    """把权利要求书切成 {项号: 正文}。跨行的权利要求归入其编号行。"""

    claims: dict[int, str] = {}
    current: int | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        match = CLAIM_HEAD_RE.match(line)
        if match:
            if current is not None:
                claims[current] = "\n".join(buffer).strip()
            current = int(match.group(1))
            if current in claims:
                raise LedgerError(f"权利要求书出现重复项号：{current}")
            buffer = [match.group(2)]
        elif current is not None and line.strip():
            buffer.append(line)
    if current is not None:
        claims[current] = "\n".join(buffer).strip()
    return claims


def split_sections(text: str) -> dict[str, str]:
    """按五个法定章节切分说明书。缺章节由形式检查器负责，此处只取存在的。"""

    marks = [(m.group(1), m.start(), m.end()) for m in SECTION_RE.finditer(text)]
    sections: dict[str, str] = {}
    for index, (name, _start, end) in enumerate(marks):
        stop = marks[index + 1][1] if index + 1 < len(marks) else len(text)
        sections[name] = text[end:stop]
    return sections


def parse_reference_list(spec_text: str) -> dict[str, str]:
    """解析"图中：100-xxx、110-yyy。"单段附图标记清单。"""

    match = REFERENCE_LIST_RE.search(spec_text)
    if not match:
        return {}
    return {
        num: name.strip()
        for num, name in REFERENCE_ITEM_RE.findall(match.group(1))
    }


class Report:
    """收集 finding 并保持 ID 稳定。"""

    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []

    def add(
        self,
        rule_id: str,
        target: str,
        status: str,
        problem: str,
        remedy: str,
    ) -> None:
        self.findings.append(
            {
                "finding_id": f"FL{len(self.findings) + 1:04d}",
                "rule_id": rule_id,
                "target_id": target,
                "status": status,
                "problem": problem,
                "remedy": remedy,
            }
        )

    def fail(self, rule_id: str, target: str, problem: str, remedy: str) -> None:
        self.add(rule_id, target, "DETERMINISTIC_FAIL", problem, remedy)

    def review(self, rule_id: str, target: str, problem: str, remedy: str) -> None:
        self.add(rule_id, target, "REVIEW_REQUIRED", problem, remedy)


def check_classification(ledger: dict[str, Any], report: Report) -> None:
    """分类与落点必须自洽，且必须存在至少一个区别特征。"""

    distinguishing = 0
    for feature in ledger["features"]:
        fid = feature["feature_id"]
        classification = feature["classification"]
        sites = feature.get("claim_sites") or []
        if classification == "fallback_only" and sites:
            report.fail(
                "CN-LEDGER-CLASS-001",
                fid,
                f"特征 {fid} 标为 fallback_only 却登记了权利要求落点",
                "改为 preamble 或 distinguishing，或清空 claim_sites",
            )
        if classification in {"preamble", "distinguishing"} and not sites:
            report.fail(
                "CN-LEDGER-CLASS-001",
                fid,
                f"特征 {fid} 标为 {classification} 却没有任何权利要求落点",
                "补登 claim_sites，或降级为 fallback_only",
            )
        for site in sites:
            part = site.get("part")
            if classification == "preamble" and part != "preamble":
                report.fail(
                    "CN-LEDGER-CLASS-002",
                    f"{fid}@claim{site.get('claim_number')}",
                    f"特征 {fid} 是前序特征，却被登记在权利要求特征部分",
                    "把该特征移入前序部分，或重新判定其分类",
                )
            if classification == "distinguishing" and part == "preamble":
                report.fail(
                    "CN-LEDGER-CLASS-002",
                    f"{fid}@claim{site.get('claim_number')}",
                    f"特征 {fid} 是区别特征，却被登记在权利要求前序部分",
                    "把该特征移入特征部分，或重新判定其分类",
                )
        if classification == "distinguishing":
            distinguishing += 1
            if not str(feature.get("technical_effect", "")).strip():
                report.review(
                    "CN-LEDGER-EFFECT-001",
                    fid,
                    f"区别特征 {fid} 未记载技术效果",
                    "补写该区别特征实际带来的技术效果；三步法第二步据此重述实际解决的技术问题",
                )
            verdict = (feature.get("prior_art_status") or {}).get("verdict")
            if verdict == "disclosed":
                report.fail(
                    "CN-LEDGER-PRIOR-001",
                    fid,
                    f"特征 {fid} 被判定为已被现有技术公开，却仍作为区别特征",
                    "改判为 preamble，或下沉为从属权利要求限定后重新分类",
                )
            if verdict in (None, "not_searched"):
                report.review(
                    "CN-LEDGER-PRIOR-002",
                    fid,
                    f"区别特征 {fid} 没有检索判定",
                    "补充 prior_art_status.verdict；未检索的区别特征不能支撑创造性论证",
                )
    if distinguishing == 0:
        report.fail(
            "CN-LEDGER-CLASS-003",
            "ledger",
            "台账中没有任何 distinguishing 特征",
            "至少标注一个区别特征；全部特征均与最接近现有技术共有意味着不存在保护边界",
        )


def check_claims(ledger: dict[str, Any], claims: dict[int, str], report: Report) -> None:
    """台账与权利要求双向对账。"""

    normalized = {num: normalize(text) for num, text in claims.items()}
    covered: set[int] = set()

    for feature in ledger["features"]:
        fid = feature["feature_id"]
        for site in feature.get("claim_sites") or []:
            number = site.get("claim_number")
            if not isinstance(number, int):
                report.fail(
                    "CN-LEDGER-CLAIM-001",
                    fid,
                    f"特征 {fid} 的 claim_number 不是整数",
                    "修正为权利要求项号",
                )
                continue
            if number not in claims:
                report.fail(
                    "CN-LEDGER-CLAIM-001",
                    f"{fid}@claim{number}",
                    f"特征 {fid} 登记在权利要求 {number}，但权利要求书没有该项",
                    "修正项号，或补写该项权利要求",
                )
                continue
            covered.add(number)
            verbatim = site.get("verbatim")
            if verbatim and normalize(verbatim) not in normalized[number]:
                report.fail(
                    "CN-LEDGER-CLAIM-002",
                    f"{fid}@claim{number}",
                    f"特征 {fid} 登记的权利要求 {number} 原文片段在该项中找不到",
                    "按权利要求书实际用词更新 verbatim，或修正权利要求",
                )
            elif not verbatim:
                report.review(
                    "CN-LEDGER-CLAIM-003",
                    f"{fid}@claim{number}",
                    f"特征 {fid} 在权利要求 {number} 没有登记原文片段，无法逐字核对术语一致性",
                    "补写 verbatim",
                )

    for number in sorted(set(claims) - covered):
        report.fail(
            "CN-LEDGER-CLAIM-004",
            f"claim{number}",
            f"权利要求 {number} 没有任何台账特征落点",
            "为该项登记对应特征；权利要求中的每一个限定都必须在台账中有来源",
        )


def check_specification(ledger: dict[str, Any], spec_text: str, report: Report) -> None:
    """台账登记的说明书落点必须能在对应章节里检索到。"""

    sections = split_sections(spec_text)
    normalized_sections = {name: normalize(body) for name, body in sections.items()}
    normalized_all = normalize(spec_text)

    for feature in ledger["features"]:
        fid = feature["feature_id"]
        if normalize(feature["name"]) not in normalized_all:
            report.fail(
                "CN-LEDGER-SPEC-001",
                fid,
                f"特征 {fid} 的规范名称“{feature['name']}”在说明书全文中找不到",
                "在说明书中使用该规范名称，或按说明书实际用词更新台账；权利要求与说明书必须使用完全相同的名词",
            )
        for index, site in enumerate(feature.get("spec_sites") or [], start=1):
            section = site.get("section")
            anchor = site.get("anchor", "")
            if section not in normalized_sections:
                report.fail(
                    "CN-LEDGER-SPEC-002",
                    f"{fid}#{index}",
                    f"特征 {fid} 登记的章节“{section}”在说明书中不存在",
                    "修正章节名，或补写该章节",
                )
                continue
            if normalize(anchor) not in normalized_sections[section]:
                report.fail(
                    "CN-LEDGER-SPEC-003",
                    f"{fid}#{index}",
                    f"特征 {fid} 在“{section}”中的定位串找不到：{anchor}",
                    "按说明书实际文字更新 anchor，或把该特征写入说明书",
                )

        if feature["classification"] == "fallback_only":
            in_implementation = any(
                site.get("section") == "具体实施方式"
                for site in feature.get("spec_sites") or []
            )
            if not in_implementation:
                report.review(
                    "CN-LEDGER-SPEC-004",
                    fid,
                    f"特征 {fid} 仅作为第三十三条弹药保留，却未落在具体实施方式",
                    "把被砍出权利要求的方案完整写入具体实施方式；答复审查意见时只能从原始记载中取弹药",
                )


def check_drawings(ledger: dict[str, Any], spec_text: str, report: Report) -> None:
    """附图标记清单与台账互为全集；步骤号不得混入附图标记清单。"""

    listed = parse_reference_list(spec_text)
    ledger_components: dict[str, tuple[str, str]] = {}
    ledger_steps: set[str] = set()

    for feature in ledger["features"]:
        fid = feature["feature_id"]
        for site in feature.get("drawing_sites") or []:
            kind = site.get("mark_kind")
            mark = str(site.get("mark", "")).strip()
            if kind == "component":
                label = site.get("label") or feature["name"]
                previous = ledger_components.get(mark)
                if previous and previous[1] != label:
                    report.fail(
                        "CN-LEDGER-FIG-001",
                        f"mark{mark}",
                        f"附图标记 {mark} 被登记了两个名称：“{previous[1]}”与“{label}”",
                        "同一标记只能对应一个技术对象",
                    )
                ledger_components[mark] = (fid, label)
            elif kind == "step":
                ledger_steps.add(mark)

    for mark, (fid, label) in sorted(ledger_components.items()):
        if mark not in listed:
            report.fail(
                "CN-LEDGER-FIG-002",
                f"mark{mark}",
                f"特征 {fid} 的附图标记 {mark} 未出现在“图中：…”附图标记清单中",
                "把该标记补入附图标记清单",
            )
        elif normalize(listed[mark]) != normalize(label):
            report.fail(
                "CN-LEDGER-FIG-003",
                f"mark{mark}",
                f"附图标记 {mark} 的清单名称“{listed[mark]}”与台账名称“{label}”不一致",
                "使清单名称与说明书正文首次出现处逐字一致",
            )

    for mark in sorted(set(listed) - set(ledger_components)):
        if mark in ledger_steps:
            report.fail(
                "CN-LEDGER-FIG-004",
                f"mark{mark}",
                f"{mark} 在台账中是方法步骤号，却被写进了附图标记清单",
                "步骤号不进附图标记清单；清单只登记部件标记",
            )
        else:
            report.fail(
                "CN-LEDGER-FIG-005",
                f"mark{mark}",
                f"附图标记清单中的 {mark}-{listed[mark]} 在台账中没有对应特征",
                "为该标记登记特征，或从清单中删除",
            )

    for mark in sorted(ledger_steps & set(listed)):
        # 已在上一循环覆盖；此处仅保证步骤号与部件标记不冲突。
        if mark in ledger_components:
            report.fail(
                "CN-LEDGER-FIG-006",
                f"mark{mark}",
                f"{mark} 同时被登记为部件标记和方法步骤号",
                "部件标记与步骤号必须使用互不重叠的编号空间",
            )

    # 步骤号与部件标记落在同一百位区间时，任何按数字做的自动核对都会误报。
    # 这不是法律缺陷，但它让"图上标记与正文是否一致"无法被机器验证。
    component_blocks = {
        int(mark) // 100 for mark in ledger_components if mark.isdigit()
    }
    for step in sorted(ledger_steps):
        digits = re.sub(r"\D", "", step)
        if not digits:
            continue
        block = int(digits) // 100
        if block in component_blocks:
            report.review(
                "CN-LEDGER-FIG-007",
                f"step{step}",
                f"步骤号 {step} 的数字落在部件标记的 {block}00 区间内，"
                "按数字做的图文自动核对会把两者混为一谈",
                f"把步骤号移出 {block}00 区间，或为部件标记与步骤号约定互不重叠的编号空间",
            )


def render_table(ledger: dict[str, Any]) -> str:
    """渲染人类可读的区别特征表。"""

    lines: list[str] = []
    lines.append("# 区别特征表")
    lines.append("")
    lines.append(f"案件：{ledger['case_id']}　生成时间：{ledger['generated_at']}")
    lines.append("")
    lines.append(
        "本表是全案技术特征的唯一台账。权利要求书、说明书和说明书附图由本表派生，"
        "三者的一致性以本表为裁决标准。本表不构成新颖性、创造性或授权前景判断。"
    )
    lines.append("")

    search = ledger.get("search_status") or {}
    if search:
        lines.append("## 检索状态")
        lines.append("")
        lines.append(f"- CNIPA 人工检索：{search.get('cnipa_manual_search', '未声明')}")
        lines.append(f"- 声明：{search.get('statement', '')}")
        if search.get("as_of_date"):
            lines.append(f"- 截止日期：{search['as_of_date']}")
        lines.append("")

    prior_art = ledger.get("closest_prior_art") or []
    lines.append("## 最接近的现有技术")
    lines.append("")
    if prior_art:
        lines.append("| 文献号 | 名称 | 角色 | 备注 |")
        lines.append("|---|---|---|---|")
        for doc in prior_art:
            lines.append(
                f"| {doc['doc_id']} | {doc['title']} | {doc['role']} | {doc.get('note', '')} |"
            )
    else:
        lines.append("未登记最接近现有技术。空列表不等于不存在现有技术，须结合检索状态阅读。")
    lines.append("")

    lines.append("## 特征对照")
    lines.append("")
    lines.append("| 编号 | 特征名称 | 分类 | 检索判定 | 权利要求落点 | 说明书落点 | 附图落点 |")
    lines.append("|---|---|---|---|---|---|---|")
    for feature in ledger["features"]:
        claim_sites = feature.get("claim_sites") or []
        claim_text = "、".join(
            f"权{site['claim_number']}"
            + ("（前序）" if site.get("part") == "preamble" else "（特征部分）")
            for site in claim_sites
        ) or "—"
        spec_text = "、".join(
            f"{site['section']}：{site['anchor']}"
            for site in (feature.get("spec_sites") or [])
        ) or "—"
        drawing_text = "、".join(
            f"图{site['figure']}"
            + (f" {site['mark']}" if site.get("mark_kind") != "none" else "")
            for site in (feature.get("drawing_sites") or [])
        ) or "—"
        verdict = (feature.get("prior_art_status") or {}).get("verdict")
        lines.append(
            "| {fid} | {name} | {cls} | {verdict} | {claims} | {spec} | {fig} |".format(
                fid=feature["feature_id"],
                name=feature["name"],
                cls=CLASSIFICATION_LABEL[feature["classification"]],
                verdict=PRIOR_ART_LABEL.get(verdict, "未声明"),
                claims=claim_text,
                spec=spec_text,
                fig=drawing_text,
            )
        )
    lines.append("")

    lines.append("## 区别特征与技术效果")
    lines.append("")
    distinguishing = [f for f in ledger["features"] if f["classification"] == "distinguishing"]
    if distinguishing:
        lines.append("| 编号 | 区别特征 | 技术效果 | 对比文件 |")
        lines.append("|---|---|---|---|")
        for feature in distinguishing:
            status = feature.get("prior_art_status") or {}
            docs = "、".join(status.get("cited_docs") or []) or "—"
            lines.append(
                "| {fid} | {stmt} | {effect} | {docs} |".format(
                    fid=feature["feature_id"],
                    stmt=feature["statement"],
                    effect=feature.get("technical_effect", "（未记载）"),
                    docs=docs,
                )
            )
    else:
        lines.append("未登记区别特征。")
    lines.append("")

    fallback = [f for f in ledger["features"] if f["classification"] == "fallback_only"]
    lines.append("## 仅写入说明书的退守方案（专利法第三十三条弹药）")
    lines.append("")
    if fallback:
        lines.append("| 编号 | 方案 | 说明书落点 |")
        lines.append("|---|---|---|")
        for feature in fallback:
            spec_text = "、".join(
                f"{site['section']}：{site['anchor']}"
                for site in (feature.get("spec_sites") or [])
            )
            lines.append(f"| {feature['feature_id']} | {feature['statement']} | {spec_text} |")
    else:
        lines.append("未登记仅写入说明书的退守方案。答复审查意见时可用的收窄落点将非常有限。")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="区别特征表四向对账")
    parser.add_argument("--ledger", required=True, help="feature-ledger.json 路径")
    parser.add_argument("--claims", required=True, help="权利要求书 UTF-8 文本路径")
    parser.add_argument("--specification", required=True, help="说明书 UTF-8 文本路径")
    parser.add_argument("--output", required=True, help="对账报告 JSON 输出路径")
    parser.add_argument("--table", help="区别特征表 Markdown 输出路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ledger = load_ledger(Path(args.ledger))
        claims_text = read_text(Path(args.claims), "权利要求书")
        spec_text = read_text(Path(args.specification), "说明书")
        claims = parse_claims(claims_text)
    except LedgerError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if not claims:
        print("错误：权利要求书中没有解析到任何编号权利要求", file=sys.stderr)
        return EXIT_INPUT_ERROR

    report = Report()
    check_classification(ledger, report)
    check_claims(ledger, claims, report)
    check_specification(ledger, spec_text, report)
    check_drawings(ledger, spec_text, report)

    fails = [f for f in report.findings if f["status"] == "DETERMINISTIC_FAIL"]
    reviews = [f for f in report.findings if f["status"] == "REVIEW_REQUIRED"]
    payload = {
        "schema_id": REPORT_SCHEMA_ID,
        "legal_effect": LEGAL_EFFECT,
        "case_id": ledger["case_id"],
        "counts": {
            "features": len(ledger["features"]),
            "claims": len(claims),
            "deterministic_fail": len(fails),
            "review_required": len(reviews),
        },
        "boundary": (
            "文本命中不等于得到支持，未命中也不等于缺乏支持。零 DETERMINISTIC_FAIL "
            "只表示四向登记可对账，不代表清楚、支持、必要技术特征或创造性成立。"
        ),
        "findings": report.findings,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[OK] 对账报告：{output_path}")

    if args.table:
        table_path = Path(args.table)
        table_path.parent.mkdir(parents=True, exist_ok=True)
        table_path.write_text(render_table(ledger), encoding="utf-8")
        print(f"[OK] 区别特征表：{table_path}")

    print(
        "[INFO] 特征 {} 项，权利要求 {} 项，DETERMINISTIC_FAIL {} 条，REVIEW_REQUIRED {} 条".format(
            len(ledger["features"]), len(claims), len(fails), len(reviews)
        )
    )
    for finding in fails:
        print(f"[FAIL] {finding['rule_id']} {finding['target_id']}：{finding['problem']}")
    for finding in reviews:
        print(f"[REVIEW] {finding['rule_id']} {finding['target_id']}：{finding['problem']}")

    return EXIT_DETERMINISTIC_FAIL if fails else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
