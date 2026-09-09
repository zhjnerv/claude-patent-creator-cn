# AGENTS.md

## 项目定位

本仓库是独立的中国专利 Skill 包。只实现中国专利起草、审查、附图和交付，不引入美国 MPEP RAG、向量索引或主 MCP Server。

## 规则

- 安全性 = 正确性 > 最小变更 > 可读性 > 一致性。
- 代码注释和文档使用中文，UTF-8 无 BOM。
- 中国法规则必须绑定 `references/cn-legal-sources/` 中的本地法源。
- 客观约束使用脚本和 JSON 合同验证；语义判断不得伪装成确定性结论。
- 各 Skill 按阶段加载，不得在总入口中复制全部规则正文。
- 不提交客户案件、范本 PDF、缓存、索引、凭据、DOCX/PDF/PNG 临时产物或 `__pycache__`。
- 新项目不得 import `Claude-Patent-Creator` 的 `mcp_server`；跨项目能力通过显式 provider 或结构化 JSON 传入。
- DOCX 默认只做 ZIP/XML、分节、页眉、样式、公式对象和图片数量等机器检查；只有用户明确要求视觉检查时才导出 PDF/PNG。
- 用户提供修改后的 Draw.io 范例时，必须先生成并确认 `cn-patent-drawing-style-brief/v1`；范例只传递视觉规则，技术元素、关系和 source/target 仍以 drawing brief 为准。
- 正式附图只保留 `.drawio` 和 PNG，不生成 SVG；PNG 必须由 Draw.io Desktop CLI 按 `diagram` 内容边界导出并通过白边门禁。
- 最终 PNG 变化后必须重新组装 DOCX，并运行附图—DOCX交付验证；不得沿用绑定旧图片的 Word 文件。

## 验证

- 核心与回归测试：`python3 -m pytest -q`
- 包边界检查：`python3 scripts/verify_package.py`
- Skill 重大修改后运行 Skill Lint。
