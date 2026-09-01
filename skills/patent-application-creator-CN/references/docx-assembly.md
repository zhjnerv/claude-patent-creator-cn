# 中国发明专利申请文件 DOCX 组装规范

本规范用于把 `02-申请文件` 中的权利要求书、说明书、说明书摘要和说明书附图，按照用户提供的 Word 模板组装为一个可编辑 `.docx`。它不替代四文书源文件；DOCX 是从已验证源文件机械生成的交付副本。

## 触发条件

满足任一条件时执行：

- 用户要求“合并成一个 Word / DOCX”；
- 案件根目录存在 `输出模版.docx`，且用户要求按该模板输出；
- 交付要求明确包含单一 DOCX 申请文件。

未提供模板时不得猜造专用模板。可以继续交付四文书源文件，并把 DOCX 组装标记为待完成。

## 输入合同

案件目录至少包含：

```text
<案件目录>/
├─ 输出模版.docx
└─ 02-申请文件/
   ├─ 权利要求书.md
   ├─ 说明书.md
   ├─ 说明书摘要.md
   ├─ 说明书附图.md
   └─ 说明书附图/
      ├─ 图1-....png
      └─ ...
```

模板必须满足：

1. 恰好包含五个新页分节，页眉依次为“权利要求书、说明书、说明书附图、说明书摘要、摘要附图”；
2. 首段带有可复用的权利要求自动编号定义；
3. 存在 `Normal (Web)`、`Title`、`Heading 1`、`正文2`、`附图图号` 段落样式；
4. 存在 Word 内置 `Strong` 字符样式；中文 Word 界面显示为“要点”；
5. 分节内已经定义所需页边距、行号、页码、页眉和页脚。

模板合同不满足时必须 fail-fast，不得用手工加粗、手工页码或临时样式静默替代。

## Markdown 公式合同

### 推荐写法

行内公式使用：

```markdown
患者年龄为 $a$，相邻年龄档为 $a_i$ 和 $a_(i+1)$。
```

独立公式使用：

```markdown
$$
C(P,a)=C(P,a_i)+(a-a_i)×[C(P,a_(i+1))-C(P,a_i)]/(a_(i+1)-a_i)
$$
```

或者：

````markdown
```math
ED_CT=Q_CT×C_CT(P,a)
```
````

为兼容现有案件，脚本也会识别“独立成段、包含等号、无中文正文”的线性公式。新案件不得依赖模糊猜测，应优先使用 `$...$`、`$$...$$` 或 `math` 代码块明确标记。

### Word 公式要求

- 公式必须转换为 Word 原生 `m:oMath` 对象；
- 使用 Microsoft Word 的 `OMaths.Add` 和 `BuildUp` 将线性输入构建为专业格式；
- 下标、上标、分式、括号和乘号必须保持可编辑结构；
- 普通字符、图片公式和仅设置 Cambria Math 字体均不算公式转换完成；
- 转换后必须检查占位符全部消失，实际 `m:oMath` 数量与登记数量一致。

## 样式映射

| 内容 | 模板样式 |
|---|---|
| 权利要求 | 复制模板首项权利要求的段落属性和自动编号 |
| 说明书发明名称 | `Title` |
| 技术领域、背景技术、发明内容、附图说明、具体实施方式 | `Heading 1` 段落 + `Strong` 字符样式（中文界面“要点”） |
| 说明书正文 | `正文2` |
| 独立公式 | `正文2`，取消首行缩进并居中，内容为原生 Word 公式 |
| 附图及图号 | `附图图号`，图片居中、图号置于图下 |
| 摘要正文 | `正文2` |

不得仅写 `run.bold = True` 冒充“要点”样式。模板样式是事实来源，直接格式只用于公式段落的必要居中和图片尺寸。

## 附图和摘要附图

1. 从 `说明书附图.md` 的 `## 图N ...` 与紧随其后的图片链接读取图号和顺序；
2. Markdown 链接指向 SVG 时，优先使用同名 PNG 作为 Word 内嵌图；
3. 每幅说明书附图独占一页，图号放在图下，不在图面重复写图号；
4. 摘要附图编号从 `说明书摘要.md` 的“摘要附图：图N。”读取；
5. 图片使用内嵌方式，不使用浮动环绕；不得拉伸、裁剪或跨页拆分。

## 执行命令

```powershell
python skills/patent-application-creator-CN/scripts/assemble_application_docx.py `
  --case-dir "中国发明专利申请-YYYY-MM-DD-名称"
```

常用覆盖参数：

```powershell
python skills/patent-application-creator-CN/scripts/assemble_application_docx.py `
  --case-dir "<案件目录>" `
  --template "<案件目录>/输出模版.docx" `
  --source-dir "<案件目录>/02-申请文件" `
  --output "<案件目录>/发明名称-专利申请文件.docx" `
  --work-dir "<案件目录>/03-审查工作区/docx组装-YYYYMMDD-HHMMSS"
```

默认不导出 PDF/PNG，也不执行视觉确认。只有用户明确要求检查 Word 版式、逐页截图或视觉效果时，才增加 `--visual-review`：

```powershell
python skills/patent-application-creator-CN/scripts/assemble_application_docx.py `
  --case-dir "<案件目录>" `
  --visual-review
```

`--no-render` 仅作为旧调用的兼容参数保留；新流程无需使用。

## 运行依赖

- Python 3.10+；
- `python-docx`；
- 项目已有依赖 `lxml`、`Pillow`；
- Windows；
- Microsoft Word 桌面版；
- `pywin32`；
- Poppler 的 `pdftoppm`（仅在用户明确要求视觉检查时需要）。

公式存在而 Word 或 `pywin32` 不可用时必须停止。默认交付不依赖 PDF/PNG。仅当用户明确要求视觉检查时，PDF 或逐页 PNG 无法生成才属于该次视觉检查未完成；不得因此否定已经通过的 DOCX 结构校验。

## 机器验收

脚本输出 `docx-assembly-report.json`（`cn-patent-docx-assembly/v2`），至少记录：

- 模板和输出 DOCX 路径及哈希；
- 权利要求书、说明书、摘要、附图索引和每幅实际嵌入图片的路径及 SHA-256；
- 权利要求数、说明书内容项数；
- 使用“要点”样式的说明书小标题数；
- 原生 Word 公式对象数；
- 说明书附图数、内嵌图片总数；
- 分节数、页眉序列、Word 页数；
- 是否请求视觉检查；
- 用户明确要求视觉检查时生成的 PDF 和逐页 PNG 路径；
- `visual_review_completed` 状态：未请求时为 `null`，请求后初始为 `false`。

默认状态为 `STRUCTURE_VERIFIED`，表示机器结构校验已完成且未请求视觉检查。只有用户明确要求视觉检查时，脚本才生成视觉检查材料并进入 `STRUCTURE_VERIFIED_VISUAL_REVIEW_PENDING`；操作者查看每一页 PNG 后，才能在外部验收记录中把视觉复核标记为完成。

## 硬失败条件

- 模板不是五分节，或页眉顺序不符；
- 模板缺少“要点”/`Strong` 等必需样式；
- 权利要求编号不连续；
- 说明书缺少发明名称或五个法定章节；
- 摘要未指定摘要附图，或指定图号不存在；
- 附图编号不连续、图片缺失或只有不可内嵌格式；
- 公式占位符未全部转为 `m:oMath`；
- 原生公式数量与登记数量不一致；
- 任一说明书小标题未应用“要点”样式；
- 用户明确要求视觉检查时，Word 页数与逐页 PNG 数量不一致；
- DOCX ZIP 包损坏。

## 按需视觉复核清单

本节只在用户明确要求视觉检查时执行。逐页以 100% 比例检查：

- 五类页眉和每节重新起算的页码；
- 权利要求编号与行号；
- 五个说明书小标题是否为“要点”粗体；
- 所有公式是否显示为专业格式，特别是上下标、分式和幂；
- 图1至图N及摘要附图是否完整、清晰、居中；
- 是否存在文字裁切、对象重叠、孤立图号、异常空白页或字体替换。

## 新鲜度复验

组装完成后必须运行：

```bash
python skills/patent-application-creator-CN/scripts/verify_docx_assembly.py \
  --report "<案件>/03-审查工作区/docx组装-*/docx-assembly-report.json" \
  --output "<案件>/03-审查工作区/docx组装-*/docx-assembly-verification.json"
```

验证器只证明报告绑定的模板、四文书、嵌入图片和 DOCX 当前仍是同一字节版本；不证明法律实体条件或未执行的视觉检查。
