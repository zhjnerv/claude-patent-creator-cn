# Changelog

## [0.2.0] - 2026-09-06

### Added

- 新增 `scripts/install_codex_skill.py`，一条命令把完整运行时、虚拟环境和七个 Codex 文件系统 Skill 安装到 `${CODEX_HOME:-$HOME/.codex}`。
- `cn-patent-workflow` 成为统一入口，按阶段读取并调用六个专业子 Skill。
- DOCX 组装器直接生成可编辑 OMML 原生公式，Linux/macOS 不再依赖 Microsoft Word COM；视觉检查使用 LibreOffice 导出 PDF。

### Changed

- 所有 Skill 名称统一为 Codex 校验要求的全小写 hyphen-case。
- 修复 setuptools 自动包发现，使 `pip install -e '.[dev,docx]'` 可直接安装开发环境。
- README 重写为安装、Skill 职责、完整流程、失效传播和跨平台 DOCX 说明。

## [0.1.0] - 2026-08-29

### Added

- 从 `Claude-Patent-Creator` 独立出中国专利起草、审查、附图、DOCX 和本地法源能力。
- 新增轻量 `cn-patent-workflow` 总入口，按阶段调用既有中国专利 Skill。
- 新增独立包边界检查，禁止引入主项目 MCP、MPEP RAG、向量索引和 GPU 依赖。
## Unreleased

- 新增 `CN-CLAIM-LENGTH-001`：每项权利要求按 Word 中文字数口径不得超过 600 字，完整公式或特殊公式变量整体计 1。
- 将新案件技术台账升级为 `cn-patent-feature-ledger/v2`，增加数据流、动作阶段、方法—系统覆盖和异常终态复算。
- 新增 `cn-patent-claim-architecture/v1`，把独权载体分工、父从权继承拓扑和方法步骤边界变为强制起草门。
- 新增 `cn-patent-drawing-brief/v4`，方法流程图强制绑定权利要求架构合同，并复算步骤、判断节点和循环返回点同构。
- 新增 `cn-patent-drawing-brief/v3` 与 `cn-patent-drawing-visual-review/v2`，绑定单图阅读合同、图文表达范围和最终 PNG 观察证据。
- DOCX 组装报告升级为 v2，并新增输入/输出哈希新鲜度验证器。
- 修复包边界检查误扫 `.git` 内部备份的问题。
- 综合审查链增加可选 `provenance_artifacts`，将检索、范本选择、阶段门、特征台账和权利要求架构纳入独立的来源哈希绑定与新鲜度校验。
