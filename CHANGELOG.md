# Changelog

## [0.1.0] - 2026-08-29

### Added

- 从 `Claude-Patent-Creator` 独立出中国专利起草、审查、附图、DOCX 和本地法源能力。
- 新增轻量 `cn-patent-workflow` 总入口，按阶段调用既有中国专利 Skill。
- 新增独立包边界检查，禁止引入主项目 MCP、MPEP RAG、向量索引和 GPU 依赖。
## Unreleased

- 将新案件技术台账升级为 `cn-patent-feature-ledger/v2`，增加数据流、动作阶段、方法—系统覆盖和异常终态复算。
- 新增 `cn-patent-drawing-brief/v3` 与 `cn-patent-drawing-visual-review/v2`，绑定单图阅读合同、图文表达范围和最终 PNG 观察证据。
- DOCX 组装报告升级为 v2，并新增输入/输出哈希新鲜度验证器。
- 修复包边界检查误扫 `.git` 内部备份的问题。
