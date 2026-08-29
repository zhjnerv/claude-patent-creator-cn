# 中国专利阶段路由表

| 当前任务 | 调用 Skill | 最少输入 | 主要输出 | 不应加载 |
|---|---|---|---|---|
| 完整申请 | `patent-application-creator-CN` | 技术交底或代码、公开日期信息 | 四文书及工作证据 | MPEP、USPTO、PCT 规则 |
| 范本和 IPC | `patent-application-creator-CN` 的检索阶段 | `technical-features.json`、候选清单 | `search-query.json`、`template-selection.json` | DOCX、附图 XML 规则 |
| 权利要求审查 | `patent-claims-analyzer-CN` | 权利要求文本 | 原始专项报告 | 完整审查指南、DOCX、附图配色 |
| 说明书审查 | `patent-specification-reviewer-CN` | 说明书、权利要求特征 | 支持矩阵和专项报告 | 检索范本、DOCX |
| 形式审查 | `patent-formalities-reviewer-CN` | manifest 和申请文件 | 形式专项报告 | 创造性检索、附图布局 |
| 综合审查 | `patent-reviewer-CN` | 三类申请文件和 manifest | review bundle、验证报告 | 范本风格、DOCX |
| 附图 | `patent-diagram-generator-ZH` | drawing brief、说明书、台账 | `.drawio`、PNG/SVG、验证报告 | 法源全文、DOCX |
| Word 交付 | `patent-application-creator-CN` 的 DOCX 阶段 | 四文书、模板 | DOCX 和组装报告 | 检索、审查指南全文 |

## 交接原则

- 检索阶段以 `cn-patent-template-search/v1`、`cn-patent-template-selection/v1` 交接。
- 起草阶段以 `cn-patent-feature-ledger/v1`、`cn-patent-stage2-gate/v2` 交接。
- 附图阶段以 `cn-patent-drawing-brief/v2` 和最终验证报告交接。
- 审查阶段以 `cn-patent-review-raw-report/v2` 和 review bundle 交接。
- DOCX 阶段只消费已经通过前序门禁的四文书，不反向修改技术事实。
