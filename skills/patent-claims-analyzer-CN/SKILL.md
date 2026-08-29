---
name: patent-claims-analyzer-CN
description: 审查中国发明专利权利要求的编号、引用候选、草稿占位和有限术语线索；不代替中国专利法律语义或现有技术审查。
---

# 中国发明专利权利要求原始检查

本技能只产生 CN v2 的确定性原始报告，所有输出均为 `legal_effect = ADVISORY_ONLY`。它不判定清楚性、支持、必要技术特征、单一性、新颖性、创造性、实用性或授权结果。

## 共享本地法源（执行前读取）

涉及中国专利法律规则、条款或审查方法时，优先读取仓库内的统一法源，不再为已收录内容默认联网搜索：

- 法源先读取 `${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/cn-legal-sources/source-index.json`，再按主题读取分章；不得默认加载 `guide-full.md`。
- 专利法：`${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/cn-legal-sources/专利法(2020-10-17).md`
- 专利法实施细则：`${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/cn-legal-sources/专利法实施细则(2023-12-21).md`
- 审查指南全文：`${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/cn-legal-sources/审查指南2026MD/guide-full.md`
- 审查指南分章：`${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/references/cn-legal-sources/审查指南2026MD/chapters/`
- 统一法源目录：`${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/patent-reviewer-CN/references/cn-source-catalog.md`

本地文本用于条款和章节目定位。只有核对后续修订、施行状态，或处理本地文本缺失与冲突时才联网，并优先使用 CNIPA 官方来源。

## 输入和运行

仅接受 UTF-8 无 BOM 的纯文本权利要求书。PDF、DOCX、扫描件和仅图片内容不在本技能输入范围。运行时仅使用 Python 标准库：

```bash
python "${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/patent-claims-analyzer-CN/scripts/check_claims_cn.py" \
  --input "<权利要求书.txt>" \
  --output "<claims-raw-report.json>"
```

`--output` 必须与输入和其他证据路径分离；脚本先写同目录临时文件、`fsync`，再在第二次别名检查通过后原子替换。

## CN v2 原始报告

报告 schema 为 `cn-patent-claims-raw-report/v2`，顶层字段严格遵循 `cn-review-contract-v2.json` 的 `raw_report` 白名单。finding 使用稳定 `finding_id`，gap 使用稳定 `gap_id`；下游只能通过 origin ID 一对一继承，不能删除、重复、合并或降级原始 `DETERMINISTIC_FAIL` 和 `REVIEW_REQUIRED`。

引用引导语只能产生 `dependent_candidate` 或 `dependent_unresolved`。脚本不得仅因“根据/按照/如 + 权利要求”确认从属关系，也不得把候选引用纳入确定性自引用、向后引用或循环结论。

## 资源和退出码

- `0`：工具完成，仍不表示法律结论。
- `2`：原始报告含 `DETERMINISTIC_FAIL`。
- `3`：路径、文件或 UTF-8 无 BOM 校验失败。
- `4`：资源限制失败；不产生法律 finding 或部分报告。

资源边界包括 4 MiB 输入、20,000 项权利要求、1,000,000 编号、100,000 条引用边、2,048 祖先深度、5,000 条 finding/gap 与 16 MiB 原始报告输出。检查器使用有界迭代图算法，禁止以极大编号构造连续编号集合。

## 后续语义审查

按 [规则矩阵](references/claims-rule-matrix.md) 和 CN v2 规范建立独立语义证据。材料或能力不足必须保留为 structured gap / `INCONCLUSIVE`，不能转化为 `NO_ISSUE_FOUND`。
