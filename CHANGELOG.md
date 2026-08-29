# Changelog

## [0.1.0] - 2026-08-29

### Added

- 从 `Claude-Patent-Creator` 独立出中国专利起草、审查、附图、DOCX 和本地法源能力。
- 新增轻量 `cn-patent-workflow` 总入口，按阶段调用既有中国专利 Skill。
- 新增独立包边界检查，禁止引入主项目 MCP、MPEP RAG、向量索引和 GPU 依赖。
