# 调用 drawio-skill 的执行约定

`patent-diagram-generator-ZH` 是专利领域适配层，不维护第二套通用 Draw.io 画法。实际制图必须使用当前环境中的 `drawio-skill`。

## 依赖发现

1. 从可用 Skill 列表定位 `drawio-skill` 并读取其 `SKILL.md`。
2. 按需读取其：
   - `references/diagram-types.md`
   - `references/xml-authoring.md`
   - `references/autolayout.md`
   - `references/troubleshooting.md`
3. 检测 Draw.io Desktop CLI：`drawio --version`，再尝试 `draw.io --version`。
4. `drawio-skill` 或官方 CLI 不可用时，停在已校验的 `drawing-brief.json`，报告缺失依赖；不得退回自制 Pillow、SVG 或浏览器截图渲染并声称正式附图完成。

## Authoring mode

- 标准流程、状态、时序等图型：优先使用 `drawio-skill` 推荐的原生生成方式。
- 需要专利部件标记、固定节点 ID、精确路由或复杂容器：读取 `xml-authoring.md`，手写或程序生成原生 XML。
- 超过约15个节点、层级或连线较多：优先使用 `drawio-skill/scripts/autolayout.py` 形成候选布局，再按专利要求人工调整；不要直接用大量绝对坐标硬凑。
- 申请文件通常不直接使用 Mermaid 转换结果，因为节点 ID、附图标记、线型和旁置标签需要严格控制；只有简单图且转换后仍满足交接合同时才可使用。

## 方法流程图文字来源

使用 `cn-patent-drawing-brief/v4` 时，方法流程图必须先读取其绑定的 `claim-architecture.json`：

- 每个步骤框使用 `step_bindings[].claim_action`，图框文字为步骤号加该动作原文；
- 判断框使用 `decision_bindings[].condition`；
- 循环边使用 `loop_bindings` 规定的起点、返回步骤和条件；
- 不得为缩短文字自行概括、合并两个步骤或改变循环归属；
- 文字过长时扩大节点、增加画布高度或拆图，不得改写技术动作。

## ID 与可追溯性

- 每个技术元素的 `mxCell id` 使用绘图合同中的 `elements[].id`。
- 每条技术关系的 edge ID 使用 `relations[].id`。
- 关系标签节点 ID 固定为 `label-<relation-id>`。
- 容器和纯装饰节点使用 `container-*`、`frame-*` 或 `decor-*` 前缀。
- 不得新增合同中不存在的技术元素或关系；需要补充时先回到专利起草端修改合同和来源文件。

## 关系标签

正确结构：

```text
source ─────────→ target
              是（旁置独立文字节点）
```

禁止：

```text
source → label → target
```

禁止把文字写入 edge `value`。标签可编辑但不参与路由。

## 官方导出

预览图由 `drawio-skill` 官方 CLI 导出，不嵌入 XML：

```bash
drawio -x -f png --size page --width 2000 --border 10 \
  -o preview/图1.png 02-申请文件/说明书附图/图1.drawio
```

最终图使用本 Skill 的薄包装器，它仍调用同一 Draw.io Desktop CLI，并写入 DPI 与哈希报告：

```bash
python scripts/export_patent_drawio.py \
  --input 02-申请文件/说明书附图/图1.drawio \
  --png 02-申请文件/说明书附图/图1.png \
  --svg 02-申请文件/说明书附图/图1.svg \
  --dpi 300 \
  --report 03-审查工作区/附图/图1-export.json
```

`.drawio` 是唯一母版；最终 PNG/SVG 必须由当前母版的官方 CLI 输出，不能由另一套 Pillow/canvas/自绘代码产生。

## 迭代

1. 运行 `drawio-skill/scripts/validate.py --strict --json`。
2. 用官方 CLI 输出宽度不超过2000像素的预览 PNG。
3. 查看预览，检查文字、线路、箭头和配色。
4. 修改 `.drawio`，重复验证与预览；不得只修 PNG。
5. 视觉通过后输出最终 PNG/SVG。
6. 创建 `cn-patent-drawing-visual-review/v2` 的 `visual-review.json`，绑定当前 drawing brief、export report 和最终 PNG 的 SHA-256，并记录 100% 与缩小比例下的逐项观察。
7. 运行 `verify_patent_drawings.py`，通过后才交回专利起草工作流。
