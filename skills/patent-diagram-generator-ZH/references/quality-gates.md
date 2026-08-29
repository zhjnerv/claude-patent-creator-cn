# 中国专利附图质量门禁

## 生产者与验证者

- **技术内容生产者**：专利起草工作流，输出 `cn-patent-drawing-brief/v2`。
- **图面生产者**：`drawio-skill`，输出 `.drawio` 和官方 CLI 导出图。
- **结构验证器**：`drawio-skill/scripts/validate.py --strict --json`。
- **专利领域验证器**：`scripts/verify_patent_drawings.py`，复算合同、标记、拓扑、配色、导出和视觉记录。
- **视觉验证者**：人工或具备视觉能力的独立审阅者，查看官方 CLI 导出的最终 PNG，写入 `cn-patent-drawing-visual-review/v1`。

生产者不得给自己签发最终 PASS。任何源文件、`.drawio` 或 PNG 变化后，旧验证记录失效。

## 硬失败

<!-- skill-lint:constraint PATENT-DRAWING-SOURCE-BINDING -->
- 绘图合同缺失、来源文件哈希陈旧或技术锚点不存在；
- `drawio-skill` 或 Draw.io Desktop CLI 不可用，却用自制渲染器替代正式输出；
- `.drawio` 不是未压缩 `mxfile/mxGraphModel`；
<!-- skill-lint:constraint PATENT-DRAWING-TECH-COVERAGE -->
- 合同元素或关系缺失，或图中新增无来源的技术元素/关系；
- 部件标记或步骤号错误、重复或混用；
- 图号或标题写入画布；
<!-- skill-lint:constraint PATENT-DRAWING-DIRECT-CONNECTOR -->
- 边带文字，或可见文字节点作为边端点/中继；
- 应直连的关系被拆为多条边，或出现自交、折返、重叠、无意义环绕；
- 线路穿过无关节点、标签或容器标题；
<!-- skill-lint:constraint PATENT-DRAWING-OFFICIAL-EXPORT -->
- Draw.io 官方 CLI 导出报告缺失，或报告源 SHA 与当前 `.drawio` 不一致；
- 最终 PNG/SVG 哈希与导出报告不一致；
<!-- skill-lint:constraint PATENT-DRAWING-VISUAL-BINDING -->
- 视觉复核缺失、未批准或绑定旧 PNG；
<!-- skill-lint:constraint PATENT-DRAWING-COLOR -->
- 使用渐变、阴影、暗色背景、过量颜色，或颜色成为唯一语义载体；
- 同一申请的附图风格、字体、编号方式或配色无理由漂移。

## 机器检查与视觉检查边界

机器可检查：XML结构、ID、来源哈希、标记、直接边、显式路由、自交/重叠、颜色数量、Draw.io CLI导出证据、PNG尺寸/DPI和记录新鲜度。

视觉必须检查：实际字体替换、文字裁切、标签是否靠近正确分支、自动路由的隐藏交叉、无意义折返/回钩、箭头方向、字体与节点一致性、整体留白、视觉层级、灰度可读性和是否“像正式专利附图”。

不得用 XML lint 代替最终 PNG 的视觉复核，也不得用视觉审阅者自报 PASS 代替哈希和结构检查。

## 回炉规则

- 技术内容或标记错误：退回专利起草端，更新说明书/台账/绘图合同。
- 布局、路由、字体或配色错误：退回 `drawio-skill` 修改 `.drawio`。
- 导出错误：重新运行 Draw.io Desktop CLI，不得编辑 PNG。
- 视觉记录陈旧：重新查看最终 PNG 并生成新记录。
