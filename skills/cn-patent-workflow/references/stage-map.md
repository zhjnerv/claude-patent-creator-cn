# 中国专利阶段路由表

| 当前任务 | 调用 Skill | 最少输入 | 主要输出 | 不应加载 |
|---|---|---|---|---|
| 完整申请 | `patent-application-creator-CN` | 技术交底或代码、公开日期信息 | 四文书及工作证据 | MPEP、USPTO、PCT 规则 |
| 范本和 IPC | `patent-application-creator-CN` 的检索阶段 | `technical-features.json`、候选清单 | `search-query.json`、`template-selection.json` | DOCX、附图 XML 规则 |
| 权利要求审查 | `patent-claims-analyzer-CN` | 权利要求文本 | 原始专项报告 | 完整审查指南、DOCX、附图配色 |
| 说明书审查 | `patent-specification-reviewer-CN` | 说明书、权利要求特征 | 支持矩阵和专项报告 | 检索范本、DOCX |
| 形式审查 | `patent-formalities-reviewer-CN` | manifest 和申请文件 | 形式专项报告 | 创造性检索、附图布局 |
| 综合审查 | `patent-reviewer-CN` | 三类申请文件和 manifest | review bundle、验证报告 | 范本风格、DOCX |
| 起草完整性门 | `patent-application-creator-CN` 的台账脚本 | feature ledger v2、权利要求、说明书 | 数据流/方法—系统/异常闭合报告 | DOCX、视觉审查 |
| 附图 | `patent-diagram-generator-ZH` | drawing brief v3、说明书、台账 | `.drawio`、PNG/SVG、visual review v2、验证报告 | 法源全文、DOCX |
| Word 交付 | `patent-application-creator-CN` 的 DOCX 阶段 | 已过门四文书、模板 | DOCX、组装报告、新鲜度验证 | 检索、审查指南全文 |

## 交接原则

- 检索阶段以 `cn-patent-template-search/v1`、`cn-patent-template-selection/v1` 交接。
- 起草阶段以 `cn-patent-feature-ledger/v2`、`cn-patent-stage2-gate/v2` 交接。
- 附图阶段以 `cn-patent-drawing-brief/v3`、`cn-patent-drawing-visual-review/v2` 和最终验证报告交接。
- 审查阶段以 `cn-patent-review-raw-report/v2` 和 review bundle 交接。
- DOCX 阶段只消费已经通过前序门禁的四文书，不反向修改技术事实。

## 失效传播

- 权利要求、说明书或台账变化：重跑起草完整性门，重建 drawing brief，并使附图验证、综合审查和 DOCX 证据失效。
- Draw.io 母版变化：重新官方导出、重新视觉复核、重新附图验证和 DOCX 组装。
- 最终 PNG 变化：重新视觉复核、附图验证和 DOCX 组装。
- 任一四文书或嵌入图片变化：重新生成 DOCX 并运行 `verify_docx_assembly.py`。
