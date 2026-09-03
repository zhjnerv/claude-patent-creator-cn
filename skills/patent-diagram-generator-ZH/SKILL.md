---
name: patent-diagram-generator-ZH
version: "4.0.0"
description: 中国专利说明书附图的领域适配与验收 Skill。应在从权利要求书、说明书和区别特征台账生成或修改中国发明/实用新型附图时使用：先冻结图号、技术元素、部件标记、步骤号和关系，形成 cn-patent-drawing-brief/v4，再调用 drawio-skill 完成专业布局、原生 .drawio 制作、Draw.io Desktop CLI 导出和视觉迭代，最后执行专利图文一致性与候选绑定验收。不要用于一般商业图表，也不要在本 Skill 内另造一套 Draw.io 布局或 PNG 渲染器。
allowed-tools: Bash, Read, Write
---

# 中国专利附图适配器 v4

本 Skill 负责**画什么、不能画错什么、如何验收**；`drawio-skill` 负责**怎样用 Draw.io 把图画好**。

```text
专利起草工作流
  → 冻结技术事实与附图合同
  → patent-diagram-generator-ZH（领域适配）
  → drawio-skill（布局、原生XML、官方CLI导出、视觉迭代）
  → patent-diagram-generator-ZH（图文一致性和最终验收）
  → DOCX组装
```

本项目不依赖原 `Claude-Patent-Creator` 的 `mcp_server`。如调用方另有 XML 辅助库，只能作为结构辅助，不能代替 `drawio-skill` 的专业制图与 Draw.io 官方渲染。

## 依赖与停止条件

1. 当前环境必须提供 `drawio-skill`。先读取其 `SKILL.md`；按图型需要再读 `references/diagram-types.md`、`references/xml-authoring.md`、`references/autolayout.md` 和 `references/troubleshooting.md`。
2. 必须存在 Draw.io Desktop CLI（`drawio` 或 `draw.io`）。
3. 任一依赖缺失时，只能交付已校验的绘图合同并报告阻塞；不得改用 Pillow、浏览器截图、独立 SVG/canvas 或第二套坐标模型冒充正式导出。
4. 所有输出写入用户指定案件目录，不得把客户案件或图面产物写入 Skill 目录。

完整调用和官方导出规则见 `references/drawio-execution.md`。

## 所需权限与安全说明

- 本Skill需要读取案件目录中的权利要求、说明书、JSON合同和附图，并在用户指定案件目录写入 `.drawio`、PNG/SVG及验证报告；不扫描案件目录之外的客户材料。
- 正式导出和复验会以参数数组、`shell=False`调用本机已安装的 Draw.io Desktop CLI、Python验证脚本和 `drawio-skill`；不会执行附图文字或案件JSON中的命令。
- Windows下只读取 `LOCALAPPDATA` 以定位标准 Draw.io Desktop 安装路径，不读取账号、令牌、密码或凭据文件。
- 默认不联网、不自动安装软件、不上传申请文件。Draw.io或`drawio-skill`缺失时按停止条件报告阻塞。
- 所有输入路径必须经过案件目录边界检查；验证器不得修改客户源文件或以编辑导出PNG绕过母版问题。

## 输入合同

专利起草端先生成 `cn-patent-drawing-brief/v4`，schema：

`references/patent-drawing-brief-schema-v4.json`；v2/v3 仅用于旧案件回放。v4必须额外绑定已通过验证的 `cn-patent-claim-architecture/v1`

最少绑定：

- 当前权利要求书、说明书、`feature-ledger.json`、`claim-architecture.json` 的路径与 SHA-256；
- 每幅图的图号、名称、图型、唯一 `primary_question`、阅读方向、层级和复杂度预算；
- 每个技术元素的稳定 ID、规范名称、部件标记或步骤号、来源锚点；
- 方法流程图逐项登记 `method_claim_number`、`step_bindings`、`decision_bindings` 和 `loop_bindings`；
- 每条关系的 source、target、类型、优选方向、独立 `route_channel` 和是否必须直连；
- 正常/异常出口，以及说明书声称该图表达的元素 ID、关系 ID 和原文锚点；
- `.drawio`、预览图、最终 PNG/SVG、导出报告的目标路径；
- 配色策略和视觉复核文件路径。

先运行：

```bash
python scripts/validate_drawing_brief.py \
  --brief "<案件>/03-审查工作区/附图/drawing-brief.json" \
  --case-dir "<案件>" \
  --output "<案件>/03-审查工作区/附图/brief-validation.json"
```

退出码非零时不得制图。来源文件变化后，合同哈希失效，必须重建。

示例：`assets/patent-drawing-brief.example.json`。

## 专利领域约束

1. 技术元素和关系只能来自冻结的权利要求、说明书和区别特征台账；制图端不得补充新技术事实。
2. 部件标记在说明书中先确定，再进入图面。部件用数字，方法步骤用 `Sxxx`；二者不得混用。
3. 图号和图名只存在于文件名、Draw.io 页面名和说明书附图说明，不进入画布。
4. 每幅图只表达一个独立逻辑；复杂系统组成和复杂方法流程应拆图。
5. 元素 ID 和关系 ID 必须沿用绘图合同；关系标签节点固定使用 `label-<relation-id>`，便于机器对账。
6. 边不得携带文字。关系说明和“是/否”使用旁置独立文字节点，但文字节点不得成为边端点或中继。
7. 每项技术关系只有一条 source→target 直接边。本可竖直或水平直连时不得增加 waypoint；只有绕开无关节点时才使用显式正交路由。
8. 禁止线穿节点、线穿文字、自交、回钩、重叠、无意义环绕及箭头方向歧义。
9. 方法流程图的步骤号、顺序、动作文字、判断条件和循环返回点必须逐项来自 `claim-architecture.json`；不得因版面空间自行概括、合并或重新编号。空间不足时扩大节点、画布或拆图。
10. 权利要求、说明书或权利要求架构合同变化后，旧绘图合同、旧视觉记录和旧最终附图全部失效。

## 图型与样式

按披露重点从 `drawio-skill` 的图型中选择适合专利的子集：

- 系统/装置组成：`system_block`
- 方法和异常分支：`method_flowchart`
- 多主体端云交互：`interaction_sequence` 或 `cross_functional_flow`
- 状态转换：`state_machine`
- 数据产生、处理和存储：`data_flow`
- 物理/模块内部结构：`internal_structure`
- 网络布置：`network_topology`
- 具有技术作用的数据结构：`data_structure`

避免无必要的 BPMN、完整 C4、UML class、Mind map、品牌图标和装饰性云架构。

详细选择标准、方向、间距和禁用图型见 `references/patent-diagram-types.md`。

## 配色

中国专利申请文件可使用彩色附图，但默认只允许：

- `patent_monochrome`：简单结构和线性流程的首选；
- `patent_restrained_color`：复杂软件系统、时序或多主体流程可选。

克制彩色最多三种非白填充色，使用低饱和蓝灰、绿灰、沙色和中性灰；白底、深色文字和深色边框。禁止渐变、阴影、透明叠加、暗色背景、霓虹色、手绘风和仅凭红/绿区分语义。转为灰度后仍必须完全可读。

调色板：

- `assets/patent-monochrome.json`
- `assets/patent-restrained-color.json`

## 调用 drawio-skill

将通过校验的 `drawing-brief.json` 交给 `drawio-skill`。实际制图时：

1. 依据 `diagram_type` 读取 drawio-skill 对应图型参考；
2. 为复杂图先规划层、列、泳道和路由走廊；超过约15个节点时优先用其自动布局能力形成候选，再人工调整；
3. 生成原生、未压缩的 `.drawio`；技术元素和关系使用合同 ID；
4. 运行 drawio-skill 的结构 lint；
5. 用 Draw.io Desktop CLI 输出预览 PNG；
6. 查看预览并修改 `.drawio`，直到文字、边、箭头、留白和配色通过；
7. 用官方 CLI 输出最终 PNG/SVG；不得编辑导出图来掩盖母版问题。

## 官方导出

本 Skill 的包装器只负责调用官方 CLI、写入 DPI 和生成证据报告：

```bash
python scripts/export_patent_drawio.py \
  --input "<案件>/02-申请文件/说明书附图/图1.drawio" \
  --png "<案件>/02-申请文件/说明书附图/图1.png" \
  --svg "<案件>/02-申请文件/说明书附图/图1.svg" \
  --dpi 300 \
  --report "<案件>/03-审查工作区/附图/export/图1-export.json"
```

报告必须声明 `renderer.kind=drawio_desktop_cli`，并绑定当前 `.drawio` 与导出文件 SHA-256。

## 视觉复核

查看 Draw.io 官方 CLI 导出的**最终** PNG，而不是 XML、自制渲染图或过期预览。逐图检查：

- 文字清晰、无裁切或重叠；
- 线条不交叉、不穿节点、不压文字；
- 标签靠近正确分支，且没有无意义折返、回钩或绕行；
- 箭头方向明确；
- 字体、字号、节点尺寸和间距一致；
- 图面不拥挤，留白合理，主次层级清楚；
- 彩色图克制且灰度可读；
- 图号未进入画布；
- 整体观感符合正式专利附图，而非产品宣传图。

结果写为 `cn-patent-drawing-visual-review/v2`，schema：

`references/visual-review-schema-v2.json`。记录必须绑定当前 drawing brief、当前 export report 和最终 PNG 的 SHA-256，并填写 100% 比例、缩小比例及每个检查项的具体观察文本

示例：`assets/visual-review.example.json`。

## 最终验证

```bash
python scripts/verify_patent_drawings.py \
  --brief "<案件>/03-审查工作区/附图/drawing-brief.json" \
  --case-dir "<案件>" \
  --output "<案件>/03-审查工作区/附图/final-verification.json"
```

验证器会重新读取真实产物并检查：

- 绘图合同及来源哈希；
- 元素、关系、标记和图号；
- source→target 直接连接、边标签和文字中继；
- 图型配色、渐变和阴影；
- drawio-skill `validate.py --strict`；
- Draw.io Desktop CLI 导出证据；
- PNG DPI、导出哈希和视觉复核新鲜度；
- v4合同的唯一问题、阅读层级、复杂度预算、独立线路通道、正常/异常出口和图文表达范围；
- 方法流程图与权利要求架构合同的步骤集合、动作原文、判断节点和循环返回点同构；
- v2 视觉记录的合同/导出/PNG 三重绑定、检查比例和逐项观察。

退出码非零或报告 `status != PASS` 时，不得把附图交回专利起草流程。

## 约束追踪与回归证据

`config/instruction-stability-contract.json` 将来源绑定、技术覆盖、直接连接、克制配色、官方导出和视觉绑定六类硬约束，逐项映射到主动 checker、正例和最小违规反例。`assets/stability/` 中的样本只用于 Skill 自身回归，不得作为客户案件的最终验收结果。正式声明多轮稳定性时，仍需由候选外评估者提供签名硬约束基线、至少三轮独立运行证据和 Skill Lint 回执。

## 硬失败与回炉

完整门禁见 `references/quality-gates.md`。核心规则：

- 技术/标记错误：退回专利起草端修改说明书、台账和绘图合同；
- 布局/路由/配色错误：退回 `drawio-skill` 修改 `.drawio`；
- 导出错误：重新调用 Draw.io Desktop CLI；
- 视觉记录绑定旧 PNG：重新查看最终图并复核；
- 任何一层不得通过修改 PNG 或手写 PASS 报告绕过上游问题。

## 输出

```text
<案件>/
├─ 02-申请文件/说明书附图/
│  ├─ 图1-*.drawio
│  ├─ 图1-*.png
│  └─ 图1-*.svg                    可选
└─ 03-审查工作区/附图/
   ├─ drawing-brief.json
   ├─ brief-validation.json
   ├─ preview/图1-*.png
   ├─ export/图1-export.json
   ├─ visual-review.json
   └─ final-verification.json
```
