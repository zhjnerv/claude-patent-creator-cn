# Claude Patent Creator CN

面向中国发明专利申请的轻量 Skill 包。它可以独立安装和运行，也可以作为 `Claude-Patent-Creator` 的可选中国法扩展。

## 设计边界

本仓库只包含中国专利所需的：

- 发明挖掘、检索清单、目标 IPC 与范本选择；
- 权利要求书、说明书、摘要和附图起草；
- 权利要求、说明书、形式及综合审查；
- 中国专利说明书附图领域适配；
- 四文书 DOCX 组装；
- 中国专利法、实施细则和审查指南本地法源；
- 确定性合同、验证脚本和测试。

本仓库不包含 MPEP RAG、FAISS/BM25、Embedding、PyTorch、USPTO/PCT/EPO 实体审查或主 MCP Server。

## Skill 入口

- `cn-patent-workflow`：轻量总入口，只加载当前阶段所需 Skill。
- `patent-application-creator-CN`：完整中国发明专利起草。
- `patent-reviewer-CN`：综合审查和证据绑定。
- `patent-claims-analyzer-CN`：权利要求专项审查。
- `patent-specification-reviewer-CN`：说明书专项审查。
- `patent-formalities-reviewer-CN`：形式专项审查。
- `patent-diagram-generator-ZH`：中国专利附图领域适配；名称暂时保留以兼容既有调用。

本项目不提供业务型 Slash Command。自然语言请求由 Skill description 触发，确定性步骤直接调用各 Skill 自带脚本。

## 按需加载

完整申请的阶段链为：

```text
检索与范本 → 起草与关系台账 → 数据流复算 → 权利要求架构门 → drawing brief v4 → 附图视觉验收 → 审查 → DOCX新鲜度复验
```

总入口不得一次性读取全部法源和全部 Skill。每个阶段只读取：

1. 当前阶段的 `SKILL.md`；
2. 当前阶段明确引用的规则或 Schema；
3. 当前案件工件；
4. 下一阶段所需的结构化交接文件。

审查指南优先读取分章文件；只有全文检索或章节冲突核查时才读取 `guide-full.md`。

## 可选外部能力

- `drawio-skill` 与 Draw.io Desktop CLI：仅在生成附图时需要；
- EPO OPS provider：仅在自动补全候选专利 IPC 时需要；
- `python-docx`、`lxml`、Pillow：仅在组装 DOCX 时需要；
- `pywin32`：仅 Windows 原生 Word 公式或视觉渲染时需要。

没有 EPO provider 时，范本选择仍可使用有来源的 IPC 缓存或候选输入，不会反向导入主项目。

## 本地使用

推荐将本仓库作为独立 Claude/Codex 插件加载，此时 `${CLAUDE_PLUGIN_ROOT}` 自动指向本仓库。

使用 Skill Manager 安装 `skills/` 集合时，应同时设置：

```bash
export CLAUDE_PATENT_CREATOR_CN_ROOT=/path/to/claude-patent-creator-cn
skill-manager install /path/to/claude-patent-creator-cn/skills
```

所有 Skill 路径均使用 `${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`，因此插件安装和本地 Skill 链接两种方式都可运行。

## 验证

```bash
python3 scripts/verify_package.py
python3 -m pytest -q
```

## 生成质量门

新案件使用 `cn-patent-feature-ledger/v2`、`cn-patent-claim-architecture/v1`、`cn-patent-drawing-brief/v4` 和 `cn-patent-drawing-visual-review/v2`。这些合同分别控制数据流与异常闭合、独权载体分工/父从权继承拓扑/方法步骤边界、流程图步骤同构与图文表达范围、最终 PNG 的实际视觉观察。DOCX 组装后使用 `verify_docx_assembly.py` 复算源文件、图片和输出哈希。旧版本仅用于历史案件回放。
