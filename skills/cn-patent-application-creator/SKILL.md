---
name: cn-patent-application-creator
description: 本技能应在生成中国发明专利申请文件时使用——从代码库、技术交底书或零散材料出发，完成发明挖掘、检索式生成与 CNIPA 人工检索留档、可选范本风格学习、权利要求优先撰写、说明书法定格式输出、复用 -CN 审查链验证、攻击演练、提交包组装，以及按用户提供的 Word 模板把四文书合并为含原生公式和附图的单一 DOCX；也用于在没有方案通过检索时给出有证据支撑的放弃结论。不要用于：美国临时申请、PCT 国际申请或其他辖区申请文件的起草，也不要用于复制范本技术内容、替代专利代理师判断或输出"可申报""必获授权"结论。
allowed-tools: Bash, Read, Write
---

# 中国发明专利申请文件创作技能

执行一次完整的专利战役：把用户手里的任何材料——代码库、技术交底书、零散笔记——要么变成一份可交专利代理师复核的中国发明专利申请文件包，要么变成一份有理由、有证据支撑的"为什么不申请"的说明。

本技能是 `patent-application-creator-ZH` 的中国辖区版本。战役骨架（挖掘 → 检索 → 权利要求优先 → 机器验证 → 两支红队 → 打包）沿用，但法律武器全部换成中国专利法、实施细则和审查指南；美国特有的临时申请、宽限期、IDS、微实体等内容一律不适用。

## 共享本地法源（执行前读取）

涉及中国专利法律规则、条款或审查方法时，优先读取仓库内的统一法源，不再为已收录内容默认联网搜索：

- 法源先读取 `${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/references/cn-legal-sources/source-index.json`，再按主题读取分章；不得默认加载 `guide-full.md`。
- 专利法：`${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/references/cn-legal-sources/专利法(2020-10-17).md`
- 专利法实施细则：`${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/references/cn-legal-sources/专利法实施细则(2023-12-21).md`
- 审查指南全文：`${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/references/cn-legal-sources/审查指南2026MD/guide-full.md`
- 审查指南分章：`${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/references/cn-legal-sources/审查指南2026MD/chapters/`
- 统一法源目录：`${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-reviewer/references/cn-source-catalog.md`

本地文本用于条款和章节目定位。只有核对后续修订、施行状态，或处理本地文本缺失与冲突时才联网，并优先使用 CNIPA 官方来源。

## 与美国流程的关键差异（动手前先读完这一节）

| 差异点 | 美国 | 中国 |
|---|---|---|
| 缓冲期 | 临时申请占位，12 个月内转正式 | **没有临时申请**。一旦提交就是正式申请，公布和审查时钟同时启动 |
| 自行公开 | 一年宽限期，自己先发布不致命 | 宽限期只覆盖专利法第二十四条的四种法定情形，**一般性自行发布不在其中**，公开即成为现有技术 |
| 修改空间 | 相对宽松 | 专利法第三十三条，修改不得超出原说明书和权利要求书记载的范围，答复审查意见时**只能从说明书里取弹药** |
| 客体 | 35 USC 101 / Alice | 专利法第二十五条（智力活动的规则和方法等）+ 指南第二部分第九章的技术三要素 |
| 费用杠杆 | 权利要求数与独权数 | 权利要求自第 11 项起收附加费（以现行收费标准为准）；说明书页数另有标准 |
| 后续时限 | — | 自申请日起 18 个月公布（专利法第三十四条）；自申请日起 3 年内提出实质审查请求（第三十五条） |

由此得到两条贯穿全流程的操作准则：**阶段 0 的公开审计可能直接终止战役**；**阶段 3 的说明书必须把一切将来可能用到的退守方案全部写进去**。

## 契约

- **诚实的结果就是交付物。** "以下现有技术足以击毙每个候选方案"是成功，不是失败。"这项可能授权但不值得你花这笔钱和三年时间——不申请，或者做防御性公开"同样是成功。绝不夸大一个孱弱的候选方案。
- **战役守护的是用户的钱，不只是他们的申请。** 值不值得做的问题必须在昂贵阶段之前提出，并且每当权利要求收窄时重新提出。一个只在最后才发现"篱笆很小"的战役，已经把预算花在了回答错误的问题上。
- **机器检查把关，人工验证。** 每一项被标记为低置信度的自动发现都必须人工核实；每一份"全部通过"的健康证明都必须列出运行过的检查和被跳过的检查。
- **中国是先申请制。** 同样的发明谁先申请归谁（专利法第九条）。但这条紧迫性只对**尚未发生**的第三方公开有意义——已经公开的现有技术永远无法被甩在后面。
- **发明人必须是自然人。** AI 不是发明人，用户才是。AI 负责挖掘、检索、撰写和验证。
- **本技能不输出授权前景。** 形式与结构检查通过不代表实体条件通过，任何交付物都是 `ADVISORY_ONLY`，最终必须经专利代理师复核。

## 阶段 0——受理与法定日期审计

原样接受粗略的请求。如果材料是代码库，不要索要交底书——挖掘是阶段 1 的工作。本技能的交付范围固定为权利要求书、说明书、说明书摘要和说明书附图四类技术文书，申请人、发明人、联系电话、地址、联系人及代理机构等请求书主体字段不作为起草输入，也不得阻断四文书生成。只问无法从材料推导且会影响技术文书合法性的日期事实：

1. 该技术是否已经公开、销售、展出、发表或交付第三方，以及最早发生日期；
2. 是否存在可主张优先权的在先申请（专利法第二十九条、第三十条；实施细则第三十四条至第三十七条）。

然后审计申请人自身的公开足迹——已发布产品、演示、公开仓库、营销页面、论文、招标文件——并记录首次公开日。**这一步在中国的分量远大于美国**：专利法第二十四条的宽限期只覆盖四种情形（为公共利益目的在紧急状态或非常情况下首次公开、在中国政府主办或承认的国际展览会上首次展出、在规定的学术会议或技术会议上首次发表、他人未经申请人同意泄露），各为 6 个月，且需按实施细则第三十三条声明并提交证明。**自己把产品上线、把仓库开源、把方案写进公开文档，都不在这四种之内**，公开之日该方案在中国即丧失新颖性。

审计结论若为"核心机制已公开且不属于第二十四条情形"，直接写放弃报告并停止。那份报告就是交付物。

## 阶段 1——发明挖掘

寻找具体的**技术机制**，而不是功能或特性。对于代码库，分派多个阅读者（每个子系统一个），候选方案必须（a）具体且已实现，（b）解决一个技术问题，（c）能落入 `references/distinguishing-feature-patterns.md` 六种形态之一，并且能说出它偏离了什么默认做法。为每个候选方案记录：机制（怎么做，而不是做什么）、证据位置、解决的技术问题、被击败的常规替代方案、这个差异为什么非显而易见。候选创新点在 2-C 检索定出 D1 之前只是**假设**，区别特征只能相对 D1 定义。

然后用以下筛查分类（杀掉／继续）：

- **客体筛查**（专利法第二条第二款、第二十五条；指南第二部分第一章、第九章）。纯商业规则、纯算法、纯数学方法、纯管理流程会被以"智力活动的规则和方法"驳回。判据是能否写出完整的三要素：**技术问题—技术手段—技术效果**。手段必须是遵循自然规律的技术手段（对内部性能的改进、对硬件/数据处理过程的改造），效果必须是技术效果而非商业效果。写不出三要素的候选方案降级或杀掉。涉及计算机程序的方案按指南第二部分第九章第 2、5、6 节组织撰写。
- **拥挤领域筛查**：本领域手册、标准或框架已有成熟通用做法的领域——拥挤领域不杀，但区别特征必须是耦合/时序条件/绑定/参数配比/反默认/失败驱动型，且通过抽象层级测试；机制名称本身不得作为依赖的区别特征。
- **单一性筛查**（专利法第三十一条第一款；实施细则第三十九条；指南第二部分第六章）：寻找一个被多个候选方案实例化的总的发明构思，各方案之间必须存在相同或相应的**特定技术特征**。凑不到一个构思下的，就是两件申请，不要硬塞。
- **值不值得做**：授权后能不能发现侵权（可检测性）？竞争者绕开的成本有多大？三年审查周期结束时这项技术还在不在用？

## 阶段 1-H——历史挖掘（当原始材料是 git 仓库时）

当前代码显示存在什么；历史显示它击败了什么、当时有多难、是什么时候——而且历史里藏着任何只读 HEAD 的人永远找不到的机制，因为它们死在被放弃的分支里。**在中国这条比在美国更值钱**：宽限期窄意味着"已部署=已公开"的风险高，而一个从未合并、从未部署的机制没有任何公开计时在跑。只要材料有 git 历史，就把这一轮与阶段 1 并行执行。

漏斗：

1. **穷举一切。** 镜像克隆；也取 `+refs/pull/*/head`。`git rev-list --all` 就是全集。如实说明限制：托管方只提供仍可从引用到达的提交，被强推覆盖的历史已经消失，结论只能说"托管方仍持有的内容"。
2. **按 patch-id 折叠。** `git rev-list --all | git diff-tree --stdin -p -r | git patch-id --stable`——跨分支的 cherry-pick 和 rebase 各自折叠为一条。成本随唯一补丁数伸缩，而不是分支数。（不要传 `--no-commit-id`，patch-id 需要提交行来归属补丁。）
3. **机械分类进命名桶。** 排除噪音主题（依赖／文档／合并）、仅锁文件或二进制的补丁、小型 diff——每次排除都进入一个记录其主题的桶。覆盖必须可算术对账：全集 = 已读 + 已排除。
4. **通读每一个幸存者。** 批量处理（每个 agent 约 30 个补丁，diff 上限约 7KB 并披露上限），要求每个阅读者对每个补丁返回判定和它实际看到的补丁数，按批次对账。区分**机制**与**例行事务**，并记录"该 diff 替代了什么常规方法"——这正是创造性三步法里最难补的那一栏。明确指示阅读者：绝不贬低被放弃或未完成的工作，被放弃的巧思正是目标。
5. **聚类并定位。** 跨多个提交的同一机制就是一个簇。对每条线索执行 `git branch --contains` 和默认分支可达性检查，再对照**已发布的代码**验证机制是否迁移过去了（桥接分支可能让"搁浅"提交的内容活在别处）。只有"已发布的一切中都不存在"才配得上"无公开计时"的标签。
6. **第二轮对抗性通读直到榨干。** 带着"第一轮误判了什么？"的提示重读例行事务堆，直到一轮通读找不到新东西。

提交日期与作者是构思时间的客观记录；一连串失败尝试之后的突破是创造性的客观佐证——两者在阶段 5 的三步法答辩里都用得上。幸存线索照样送进阶段 1 的筛查。

## 阶段 2——现有技术：每一个出口，对抗性地

### 2-A：生成检索清单并人工筛选范本

先把阶段 1 的幸存方案整理成 UTF-8 JSON。**查找范本之前必须先判断目标技术方案的 IPC 分类号**，并把人工判断后的分类号显式写入 `ipc_codes`；自动领域映射只能作为建议，不能替代这一判断。至少还应提供一个可检索的关键词、部件、算法、技术问题、技术方案或 CPC 分类号；能人工确定的英文词放进 `keywords_en`，不要要求脚本猜译专有名词：

```json
{
  "technical_problem": "网络抖动时分布式锁一致性下降",
  "technical_solution": "通过租约续期和版本戳校验恢复一致性",
  "key_components": ["租约管理器", "仲裁节点"],
  "algorithms": ["版本戳校验算法"],
  "field": "分布式数据处理与网络通信",
  "keywords_en": ["lease renewal", "version stamp"],
  "ipc_codes": ["G06F11/30"],
  "cpc_codes": ["G06F11/30"]
}
```

运行：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/generate_search_query.py" \
  --features "<technical-features.json>" \
  --output "<search-query.json>"
```

`search-query.json` 固定输出 `cn-patent-template-search/v1`，包含中文关键词、可确定映射的英文关键词、`untranslated_cn_terms`、IPC/CPC 建议、`target_ipc` 判定状态、可在 Google Patents Public Datasets `publications` 表执行的 BigQuery SQL，以及 CNIPA 人工检索清单。`target_ipc.status` 只有在 `technical-features.json` 显式提供 `ipc_codes` 时才为 `determined`；仅由关键词映射得到时为 `suggested`，不得进入范本排序。出现以下任一情况必须停止并修正输入：

- 输入不是 UTF-8 JSON 或字段类型错误；
- 没有任何关键词或分类号，脚本拒绝生成全表查询；
- `target_ipc.status` 不是 `determined`，却开始搜索或选择范本；
- `untranslated_cn_terms` 未人工补齐，却准备把英文检索称为已完成；
- BigQuery 结果被误当成 CNIPA 官方库检索结果。

随后在 CNIPA 专利检索及分析系统人工执行并留档检索日期、检索式、命中数和筛选理由。结果同时完成两件事：

1. 找对抗性文献，用于阶段 2-C 的逐要素攻击；
2. 形成 1—10 篇 `cn-patent-template-candidates/v1` 范本候选，逐篇给出 `technical_relevance_score`（0—1）及理由。候选优先同领域、已授权、权利要求不少于 10 项、说明书和附图完整，且申请人或代理机构质量可信（参考 `references/notable-entities.txt`）。

候选 IPC 获取顺序固定为：**EPO OPS provider → 有来源记录的分类缓存 → 候选输入**。通过 `--epo-provider-command` 或 `CN_PATENT_EPO_PROVIDER_COMMAND` 调用独立 provider，不下载 PDF，也不得反向 import 其他项目；provider 未配置、EPO 未收录或调用失败时，必须记录失败状态和降级来源。未取得逐篇 IPC 的候选不得成为推荐或最终范本。

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/rank_template_candidates.py" \
  --search-query "<search-query.json>" \
  --candidates "<template-candidates.json>" \
  --classification-cache "<可选的ipc-cache.json>" \
  --ipc-weight 0.35 \
  --output "<template-selection.json>"
```

输出 `cn-patent-template-selection/v1` 的 `template-selection.json`。默认综合得分为：技术相关性 `0.65` + IPC 相似度 `0.35`。IPC 相似度按“完全相同 → 同主组 → 同小类 → 同大类 → 同部”的层级计算。权重可按案件调整，但 `ipc_similarity` 必须保持正权重，不能退化为只看标题和摘要。人工偏离加权最高候选时，必须通过 `--selected` 和 `--selection-reason` 留下理由。

仓库没有 CNIPA 官方检索接口。人工检索未完成时必须写“未完成”，不得静默继续或声称检索穷尽。

**范本由用户确认，不由本技能替用户选定。** `template-selection.json` 只是带 IPC 证据的机器推荐；哪几篇作为撰写范本，仍须用户明确指定。用户未指定前，阶段门的 `template_selection.status` 保持 `pending`，起草不得开始。新案件必须使用 `cn-patent-stage2-gate/v2`，登记 `search_query_path`、`candidate_manifest_path` 和 `selection_report_path`；阶段门会核对输入哈希、EPO 优先尝试、候选 IPC、相似度权重和已确认风格指南是否指向同一公开号。

完整字段、评分算法、EPO 降级规则和 v2 阶段门示例见 `references/template-ipc-selection.md`。

### 2-B：提取范本风格并生成起草简报

范本全文优先通过现有 BigQuery 专利全文工具获取；无法获取时由用户提供权利要求书、说明书和可选摘要的 UTF-8 文本。每篇范本分别运行分析器：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/analyze_template_style.py" \
  --patent-number "<范本专利号>" \
  --claims "<范本权利要求书.txt>" \
  --specification "<范本说明书.txt>" \
  --abstract "<范本摘要.txt>" \
  --output "<template-style-guide.json>"
```

输出必须通过 `cn-patent-template-style/v1` 合同校验。分析器只提取权利要求数量与依赖结构、平均篇幅、说明书章节与段落分布、实施例数量与**组织方式**、描述倾向、术语/句式、附图类型与标记模式、摘要结构；它不判断范本技术价值或法律有效性。

**实施例数量必须与组织方式一并消费。** `embodiment_organization` 有三个取值：

| 取值 | 含义 | 起草含义 |
|---|---|---|
| `sectioned` | 实施例以独立标题分节，各节平行展开 | 可按数量拆成 `### 实施例N` |
| `single_flow` | 只有一条实施方式脉络，编号仅在行文中提及 | **收敛为一个实施方式**，变体作为替代路径写在同一脉络内 |
| `none` | 全文没有实施例编号 | 具体实施方式为不编号的连续叙述 |

判据是"是否存在实施例标题行"，不是"是否出现实施例三个字"。一个只输出实施例数量的风格指南无法回答说明书该长什么形态——把 `single_flow` 的范本按数量拆成 N 个平行实施例，是范本学习最容易发生也最难察觉的失真。

多篇范本必须用合成脚本产出复合指南，**不得手写**：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/merge_template_styles.py" \
  --guide "<范本1/template-style-guide.json>" \
  --guide "<范本2/template-style-guide.json>" \
  --override "<字段路径>=<新值>=<理由>=<依据>" \
  --output "<composite-template-style-guide.json>"
```

合成规则：数值取中位数，枚举取多数，列表按出现顺序去重合并；组织方式取**最保守值**（`none` < `single_flow` < `sectioned`），因为把单脉络范本误判成分节范本的代价远大于反向。任何偏离机器合成结果的人工值必须经 `--override` 提供，并携带机器值、人工值、理由和依据写入 `provenance.manual_overrides`。**手写的、无审计的复合指南一律校验失败**——手改数字而不留审计，正是错误值一路走到起草端的通道。

确定当前方案实际披露的技术特征数、变体数和可视化组件/流程数后，生成阶段 3 的唯一风格交接文件：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/style_applicator.py" \
  --style-guide "<template-style-guide.json>" \
  --available-features <技术特征数> \
  --available-variations <已披露变体数> \
  --available-components <可视化组件或流程数> \
  --output "<style-brief.json>"
```

未选择范本时省略 `--style-guide`，仍生成默认 `style-brief.json`。输入计数必须大于等于 1；风格指南缺字段、枚举非法或权利要求总数不守恒时必须失败，不得带病回退到默认风格。

`style-brief.json` 固定使用 `cn-patent-style-brief/v1`，只允许影响结构、篇幅和句法偏好。执行优先级不可倒置：

1. 本申请已披露的技术事实；
2. 中国专利法律与形式要求；
3. 现有技术检索后的权利要求边界；
4. 范本风格简报。

严禁从范本复制技术内容、凭风格建议新增未披露特征、为贴近范本删除必要技术特征，或让范本篇幅偏好覆盖 10 项以上权利要求附加费和摘要 300 字等法定/费用边界。

### 2-C：对抗性检索（原有逻辑）

只查专利不够，致命对比文件常常是产品、开源代码、标准和论文。

1. **专利文献**：本仓库的 BigQuery 检索工具（若已配置）覆盖含中国公开文本在内的全球专利。**仓库没有 CNIPA 官方检索接口**，中文关键词与分类号检索必须在 CNIPA 专利检索及分析系统人工补做，检索式、检索日期和命中结果一并留档；这条能力边界必须在文件包里明说，不得让读者以为已做过官方库穷举。
2. **抵触申请单独扫一遍**（专利法第九条；实施细则第四十七条；指南第二部分第三章第六节）。申请日以前提交、申请日以后才公布的在先申请同样破坏新颖性，而这类文献在起草时**原理上检索不到**。文件包必须把它写成一项无法消除的残余风险，而不是假装扫清了。
3. **非专利文献**：按权利要求簇分派对抗性检索，每一路都被指示去**击毙**权利要求——在位产品实际做什么、开源实现读代码、标准组织、arXiv、工程博客、公司技术文档。
4. 每一路返回逐项判定："我们有而它没有的"或"预期（破坏新颖性）"。汇总为：干净地带（写进独立权利要求）、**争议地带**（各特征单独已公开，但其耦合关系、时序条件、绑定集合或在 D1 语境下所起的作用未被任何单篇对比文件教导；中国实务中多数授权专利落在此带）、击杀区（绝不单独主张）、必读对比文件（代理师复核前必须读的）、未解决线索（被反爬拦截的页面等——上报用户，绝不无声丢弃）。

**语言纪律（不可谈判）。** 检索结果只支持"截至〔日期〕在〔已检索的出口〕中未发现预期"这种表述，并以带日期的逐要素对照表为支撑。绝不把"没有人做过""不存在现有技术""已扫清"当作事实写进任何文件。

**决策门（三分支）。** 有干净地带 → 写入独权，正常推进。只有争议地带 → 继续，但 `distinguishing` 特征必须带 `function_in_ref` 判断并进入创造性防御地图（后续 `cn-patent-inventive-step-map/v1`）。干净地带与争议地带皆无 → 输出"可授权最小方案 + 风险等级"的客户沟通稿，是否放弃由专利代理师与客户决定，流程不得自行写放弃报告终止。有幸存者 → 在**清扫后的宽度**上重跑值不值得做：干净地带总是比阶段 1 的候选窄，问题是更小的篱笆是否仍让竞争者付出代价。能被明显变体绕开的幸存者也写进该沟通稿，并给出防御性公开建议（成本近乎为零、永久有效、可用于阻断他人就同一机制在后申请）。

### 2-D：区别特征表（阶段 3 的唯一事实来源）

权利要求书、说明书和说明书附图各自持有一份技术事实副本、彼此只靠散文连接，是本工作流最深的结构性缺陷：范本学习、检索边界和起草三段各记一套特征编号，谁也对不上谁。**这三份法定文件必须由同一张台账派生。**

新案件固定使用 `cn-patent-feature-ledger/v2`（schema 见 `references/feature-ledger-schema-v2.json`）；v1 仅用于旧案件回放。v2 台账，每个特征登记一次并绑定它在三份文件中的落点：

- `classification`：`preamble`（与最接近现有技术共有，写入独权前序）／`distinguishing`（区别特征，写入特征部分或从属项）／`fallback_only`（不进权利要求，仅作第三十三条弹药写入说明书）；
- `prior_art_status.verdict`：**没有 `novel` 这个取值**。检索只支持"截至〔日期〕在〔已检索出口〕中未发现"，不支持"不存在现有技术"；
- `evidence`：来自**实现本身**的证据位置，不是挖掘 agent 的摘要；
- `flow`：逐特征记录动作阶段、输入对象、处理主体、处理动作、输出对象、下游特征和异常路径；
- `claim_data_flows`：逐项独立权利要求记录入口、顺序链、汇合点、正常出口、异常出口和存储点；
- `method_system_pairs`：复算方法独权和系统独权是否覆盖同一必要数据链，系统侧必须登记实际处理模块；
- `exception_paths`：按触发条件、分支动作、结果值、置信度、检查级终态、原因码和存储字段闭合；
- `claim_sites` / `spec_sites` / `drawing_sites`：三份文件中的落点。附图落点区分 `component`（部件标记，须进附图标记清单）与 `step`（步骤号，**不进**附图标记清单）——两者共用同一数字空间时，任何按数字做的图文自动核对都会误报。

建立台账后跑四向对账，并产出人类可读的区别特征表：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/build_feature_ledger.py" \
  --ledger "<feature-ledger.json>" \
  --claims "<权利要求书.txt>" \
  --specification "<说明书.txt>" \
  --output "<feature-ledger-report.json>" \
  --table "<区别特征表.md>" \
  --drawing-brief "<drawing-brief.json>"  # 绘图合同形成后追加复算
```

对账方向是四条，缺一不可：台账→权利要求（登记的落点在原文中确实存在）、权利要求→台账（每一项权利要求都有台账来源，没有孤儿项）、台账→说明书（每个特征在说明书有可检索到的落点）、台账↔附图标记清单（互为全集，且步骤号不混入清单）。

首次建立台账时权利要求与说明书尚未撰写，此时只需通过合同校验；阶段 3 每完成一份文件即重跑一次，阶段 5 收窄权利要求后必须重跑。**退出码 `0` 只表示四向登记可对账，不代表清楚、支持、必要技术特征或创造性成立。**

### 2-E：阶段门（未过门不得起草）

约束写成文档口号就等于没有约束。"人工检索未完成时必须写未完成"这句话，在"写了未完成再继续"的路径下字面合规——上一轮正是这样在检索未完成、范本未确认的情况下产出了权利要求和说明书，事后才补范本学习并返工三轮。

因此检索、IPC 判定、范本加权选择、用户确认和区别特征表必须变成机器状态位。新案件写进 `cn-patent-stage2-gate/v2`（schema 见 `references/stage2-gate-schema-v2.json`）；v1 只用于旧案件回放，不满足新流程的 IPC 证据要求：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/check_stage_gate.py" \
  --state "<stage2-gate.json>" \
  --workspace "<案件根目录>" \
  --output "<stage2-gate-report.json>"
```

| 状态位 | 放行条件 |
|---|---|
| `cnipa_manual_search.status` | `completed` 须附逐条检索记录；`partial`／`not_completed` 须附**用户原话**授权 |
| `template_selection.status` | `confirmed` 须列出已生成的 style-guide 并附用户原话；`declined` 须附用户原话；**`pending` 一律阻断** |
| `style_brief_path` | 存在、schema 正确、来源模式与范本确认状态一致、含 `organization` |
| `feature_ledger_path` | 存在、schema 正确、至少有一个区别特征 |

**跳过必须携带用户原话。** agent 复述的"用户已同意"不构成授权——`user_quote` 要求逐字引用，让越权在文件里留下可核对的痕迹。退出码 `2` 表示未过门，此时不得开始撰写权利要求与说明书。

## 阶段 3——权利要求优先的撰写

先读 `style-brief.json` 与区别特征表，再写权利要求和说明书；干净地带决定保护边界，风格简报只决定不冲突的结构与表达偏好。没有范本也必须读取默认简报，避免在同一申请中混用多套布局策略。简报与实现、法律规则或检索结论冲突时，必须舍弃简报建议并记录原因。

**权利要求、说明书和附图都从区别特征表派生，不各自另起炉灶。** 独权前序取 `preamble` 特征，特征部分取写入独权的 `distinguishing` 特征，其余 `distinguishing` 下沉从属项，`fallback_only` 只进说明书。任何一份文件改完即重跑 2-D 的四向对账。

**权利要求完成后必须先过数据流复算门，再写附图。** 对每项方法/系统独权按“入口→处理主体→中间结果→汇合→正常/异常出口→存储”检查；每个动词必须区分 `preconfigured`、`runtime_input`、`runtime_processing`、`runtime_output`、`postprocessing`。配置动作不得伪装成每次运行必做步骤，系统独权不得遗漏实际解析、聚合、存储等处理主体。任何异常或退守路径必须同时确定是否产生结果值、置信度、终态、原因码和存储字段。

- **独立权利要求必须记载解决技术问题的全部必要技术特征**（实施细则第二十三条第二款；指南第二部分第二章）。少写一个必要特征会被以"缺少必要技术特征"驳回，多写一个非必要特征则白白缩小保护范围——这是中国独权撰写最容易两头翻车的地方。
- **权利要求 1 控制在 400 字以内（上限，不是目标）。** 预审对“明显堆砌、非必要限缩保护范围”的判断难以量化，撰写端可控的替代做法是压缩权利要求 1：只保留解决技术问题的必要技术特征，公式、参数、符号定义和实施细节一律下沉到从属项或说明书。审查链以 `CN-CLAIM-LENGTH-002` 判定，401 字起阻断。
- **权利要求 1 句法规则。** 前序部分一句话概括与 D1 共有部分，不展开实现细节。特征部分每条写成"条件 + 动作""绑定集合"或"位置关系 + 作用"，禁止罗列实现细节。起草时对权 1 每个特征做删除测试：删掉后技术问题仍能解决的立即下沉到权 2 或后续从权——不等到阶段 5。
- **最核心的保护点放在权利要求 2，控制在 500 字以内（上限，不是目标）。** 权利要求 2 必须直接且仅引用权利要求 1，承载区别特征表中最核心的 `distinguishing` 特征，构成独权失守时的第一退守位；在 `claim-architecture.json` 的 `core_protection_point` 登记承载特征编号并经复核批准。审查链以 `CN-CLAIM-CORE-001` 检查落位、`CN-CLAIM-LENGTH-003` 判定字数，501 字起阻断。其余各项仍以 600 字为上限（`CN-CLAIM-LENGTH-001`）。三个数字都是最大限制而不是必须达到的字数：短于上限不需要补字，更不得为凑字数把非必要特征塞回权利要求。
- **前序部分＋特征部分**（实施细则第二十三条第一款）：前序写与最接近现有技术共有的特征，特征部分写区别特征。特征部分放什么，直接决定阶段 5 三步法答辩时"区别特征"这一栏长什么样。
- **从属权利要求的引用形式**（实施细则第二十二条至第二十五条；指南第一部分第一章 4.4、第二部分第二章 3.3）：编号连续、引用在前权利要求；多项从属只能**择一**引用，且不得作为另一项多项从属权利要求的引用基础。写法用"根据权利要求 N 所述的……，其特征在于……"完整形式，不用简写。
- **项数控制**：自第 11 项起收附加费（以现行收费标准为准）。被砍掉的从属方案**必须完整保留在说明书里**，否则等于永久丢弃。
- **术语一致**：同一技术对象在权利要求书与说明书中使用**完全相同**的名词；首次出现给出完整名称，其后用"所述……"回指。分析器的引用追踪和审查员都依赖这一点。
- **为第三十三条准备弹药。** 中国答复审查意见时的修改不得超出原说明书和权利要求书记载的范围。因此每一个可能的退守位置——参数范围、替代器件、可选步骤、异常分支、被合并掉的从属方案——都必须在提交前写进说明书。**说明书是这件申请一生中唯一一次装弹的机会。**
- **背景技术必须写 D1 的具体缺陷**，并与权 1 区别特征的作用一一对应；不得只写"现有技术存在不足"式的空话。**发明内容对区别特征的组合写机理链**：为什么 A+B 一起才解决技术问题、单独为何不行——这条在三步法答辩中直接构成"非显而易见的技术效果"的弹药。

**来源核实的权利要求（强制）。** 每项权利要求的每一个限定都必须对照**实现本身**验证——打开代码——而不是对照挖掘 agent 的摘要，也不是对照会过时的头注释。具体实施方式是权利要求、说明书和附图必须一致表述的裁决标准：三者必须描述**同一个**算法，否则每个变体必须明确写成单独的实施方式。绝不主张实现不具有的行为。这一致性由区别特征表的四向对账承载，不靠人工通读比对。

**实施例形态服从范本组织方式。** `style-brief.json` 的 `specification.embodiments.organization` 决定说明书形态：`sectioned` 才允许拆成 `### 实施例N`；`single_flow` 与 `none` 必须收敛为一条实施方式脉络，变体用"作为替代或者与前述实施方式组合"一类的过渡写在同一脉络内。**按实施例数量机械拆节是错的**——数量回答不了形态。简报里的 `warnings` 每一条都必须处理或记录不处理的理由。

**权利要求架构门（强制）。** 权利要求和说明书形成后、绘图合同生成前，必须建立 `cn-patent-claim-architecture/v1`（见 `references/claim-architecture-schema-v1.json` 和 `references/claim-architecture.md`），执行：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/scripts/validate_claim_architecture.py" \
  --contract "<claim-architecture.json>" \
  --case-dir "<案件根目录>" \
  --claims "<权利要求书.md>" \
  --specification "<说明书.md>" \
  --output "<claim-architecture-validation.json>"
```

该门同时执行四类检查：

1. **独权载体分工**：公式、符号定义、实施细节和控制时序逐项决定留在独权、下沉从权或留在说明书。高公式量、高符号量或跨多个执行阶段时必须由独立审查者批准；不得把“内容完整”误当成“独权简要”。
2. **父从权继承拓扑**：先合并全部父项连接边，再加入从属项新增边；同一排他端口出现不同来源时硬失败。新增中间模块不能靠从权静默替换父项的直接连接。
3. **方法步骤冻结**：逐项冻结 `S1—Sn`、动作原文、说明书锚点、判断分支和循环返回点。此后说明书流程段和附图只能消费该合同，不得另行概括或重新划分步骤。
4. **核心保护点登记**：`core_protection_point` 登记权利要求 2 承载的核心区别特征编号；验证器核对权利要求 2 直接且仅引用权利要求 1、所登记特征在台账中为 `distinguishing` 且落位权利要求 2、复核状态已批准，否则硬失败。

退出码非零时不得生成绘图合同、进入综合审查或组装 DOCX。权利要求或说明书任何字节变化都会使本合同及其下游附图证据失效。

**终态完备性。** 任何断言确定性终止、有界重试或保证结果的说明书，都必须穷举每一个终态和每一次预算转换——包括不体面的那些（机械性耗尽、全局超限兜底）——附图必须用带标签的边展示每个分支。

**附图。** 本技能不直接承担 Draw.io 布局和导出。先依据权利要求、说明书、`feature-ledger.json` 与已通过验证的 `claim-architecture.json` 生成 `cn-patent-drawing-brief/v4`，冻结图号、单图唯一问题、阅读层级、复杂度预算、技术元素、部件标记、步骤号、关系通道、正常/异常出口、正文图示声明、方法步骤绑定、判断节点、循环边、来源锚点、配色策略和输出路径；通过 `cn-patent-diagram-generator/scripts/validate_drawing_brief.py` 后，将合同交给 `cn-patent-diagram-generator`，由其调用专业 `drawio-skill` 完成实际布局、原生 `.drawio` 制作、Draw.io Desktop CLI 官方导出和视觉迭代。专利图可选黑白或克制彩色，但颜色不得成为唯一语义载体。最终必须产生 `visual-review.json` 和 `final-verification.json`，并由 `verify_patent_drawings.py` 复算来源哈希、标记、关系、路由、配色、官方导出和视觉记录；退出码非零时不得进入 DOCX 组装。附图标记的**分配**属于本阶段，不得推迟到制图端。

## 说明书输出格式（强制）

申请文件最终要进中国专利电子申请系统（CPC），正文以纯文本／XML 承载，Markdown 的表格、项目符号和多列排版在导入时会被打散或整体丢失；而说明书一经提交，格式返工要走补正程序。以下格式是强制的，不是建议。

### 章节结构

`# <发明名称>` 一级标题；随后五个法定章节各一个二级标题，顺序固定：技术领域、背景技术、发明内容、附图说明、具体实施方式（实施细则第二十条；指南第一部分第一章 4.2、第二部分第二章 2.2）。具体实施方式下的实施例用 `### 实施例N` 三级标题。说明书文件内不写请求书、权利要求书、摘要等其他文书的内容。

### "附图说明"章节

各图说明**每幅图一个自然段**，按图号升序，句式为"图N是……示意图／流程图／时序图。"：

```
图1是本发明多级DDS协同调控的高精度啁啾频率控制系统的一种双级结构示意图。

图2是本发明中协同控制模块的组成及其与两级DDS系统之间的信号连接示意图。
```

不加项目符号（`-`）、不加编号列表（`1.`）、不加表格。各图说明写完后另起一段，写附图标记清单。

### 附图标记清单（强制句式）

写成**一个自然段、一句话**，放在"附图说明"章节末尾（实施细则第二十一条；指南第一部分第一章 4.3、第二部分第二章 2.3）：

```
图中：100-高稳定参考时钟源、110-频率基准单元、120-频率合成单元、200-前级DDS系统、……、600-附加DDS系统。
```

- 以"图中："起头；每个条目是"标记-名称"，中间用半角连字符 `-`；条目之间用顿号"、"；句末用句号"。"。
- 标记按数字升序排列；下位标记紧随其父标记（100 之后接 110、120，再接 200）。
- 名称与说明书正文中该部件**首次出现处逐字一致**：正文写"高稳定参考时钟源100"，清单就写"100-高稳定参考时钟源"，不得出现"参考／参数"这类一字之差。
- 只列附图中实际出现的标记。正文有、图上没有的不列入；图上有、正文没有的，先补正文再列。

**禁止用表格承载附图标记**——Markdown 表格、Word 表格、多列排版、每条一行的列表都不行。中国专利说明书的附图标记按撰写惯例就是上面这一句话，表格既不是通行写法，也过不了 CPC 的文本导入。注意边界：说明书里出现表格本身并不违法，审查指南允许说明书含化学式、数学式和表格；被禁止的是用表格**代替**这句附图标记说明。

### 正文其余排版约束

- 法定内容不用 Markdown 列表符号承载：方法步骤写成"步骤S1：……"或"S1、……"的正文行文，部件枚举、引用关系同理。
- 引用附图统一写"如图N所示"，且该图号必须在"附图说明"中逐号列出过。
- 公式独立成段。为保证后续 Word 原生公式转换，新稿优先用 `$...$` 标记行内公式，用 `$$...$$` 或 `math` 代码块标记独立公式；不得依靠普通字符、下划线和字体外观冒充公式结构。
- 说明书摘要不超过 300 字，并指定一幅摘要附图（实施细则第二十六条；指南第一部分第一章 4.5.1、4.5.2）。

### 回扫

阶段 6 打包前对说明书做一次格式回扫："附图说明"章节里出现表格、项目符号，或附图标记被拆成多行的，都是必须修掉的格式缺陷。这三种形态已由 `check_formalities_cn.py` 做确定性筛查并输出 `WARNING`——注意它**不改变退出码**，退出码 `0` 不代表形态没问题，必须逐条读 findings。而标记名称是否与正文首次出现处逐字一致，脚本判断不了，只能靠这一遍人工回扫。

## 阶段 4——机器验证循环（复用 -CN 审查链，迭代到干净）

本技能不自带检查器，全部复用仓库内的 `-CN` 审查链。三个原始检查器只读 UTF-8 无 BOM 文本，不联网、不建索引：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-claims-analyzer/scripts/check_claims_cn.py" \
  --input "<权利要求书.txt>" --output "<claims-raw-report.json>"

python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-specification-reviewer/scripts/build_support_matrix_cn.py" \
  --specification "<说明书.txt>" --features "<候选特征.json>" --output "<specification-raw-report.json>"

python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-formalities-reviewer/scripts/check_formalities_cn.py" \
  --manifest "<application-manifest.json>" --output "<formalities-report.json>"
```

退出码统一为：`0` 工具成功执行、`2` 报告含 `DETERMINISTIC_FAIL`、`3` 输入／路径／编码／JSON 无效、`4` 资源越限。**退出码 `0` 不代表申请文件通过审查。**

组装完整申请文件后走一遍完整链（等价于 `/full-review-cn`）：

```bash
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-reviewer/scripts/build_review_bundle.py" prepare \
  --application "<prepare-input.json>" --workspace "<工作目录>"
# 在新上下文中完成独立语义审查，填写 review-input-template.json
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-reviewer/scripts/build_review_bundle.py" finalize \
  --workspace "<工作目录>" --review-input "<语义审查输入.json>" --output "<review-bundle.json>"
python3 "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/scripts/run_python.py" "${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-reviewer/scripts/verify_review_bundle.py" \
  --workspace "<工作目录>" --bundle "<review-bundle.json>" \
  --output "<bundle-verification.json>" --summary "<review-summary.md>"
```

若申请目录已经产生检索清单、范本候选与选择、阶段门、区别特征台账或权利要求架构合同，应在 `prepare-input.json` 的可选 `provenance_artifacts` 中逐项声明相对路径。审查链会把这些前置工件的字节和集合哈希冻结到 `prepare-manifest`、语义输入和 bundle；任一工件变化都必须从 prepare 重新开始。该绑定只证明流程来源可复算，不替代新颖性、创造性或其他法律判断。

迭代到零个确定性失败：每个被标记的权利要求要素都要逐字织进说明书；人工核实每一条 `REVIEW_REQUIRED` 并记录判定——人工这一轮是工作流的一部分，不是可选项。没有做过现有技术检索时，新颖性与创造性维度按契约必须保持 `INCONCLUSIVE`，这是设计上的 fail-closed，不要试图绕过。

**验证印章携带内容哈希，编辑会使它们失效。** 每条记录的检查结果必须声明其所检查工件文本的 SHA-256。之后任何编辑——加一项权利要求、动一句话——都会使该工件上的所有印章失效，打包前必须从 prepare 整链重跑。一份 README 对验证后又被编辑过的工件说"已验证"，是文件包能携带的最具破坏性的谎言。

## 阶段 5——两支红队，而不是一支

**5a. 审查员攻击演练（权利要求）。** 派出扮演 CNIPA 实质审查员的对抗性 agent 攻击最终权利要求，配备检索中的最接近对比文件，按下列顺序逐项开火。区别特征表的"区别特征与技术效果"一节就是三步法第二步的现成弹药清单，攻防双方都以它为准：

1. **新颖性（专利法第二十二条第二款；指南第二部分第三章）**：单篇对比文件逐特征比对，允许惯用手段的直接置换。找到一篇覆盖全部特征的即击毙。
2. **创造性（专利法第二十二条第三款；指南第二部分第四章）——三步法**：①确定最接近的现有技术；②确定区别特征，并据其**实际解决的技术问题**重新表述发明的技术问题（注意：这一步审查员会重新表述，不采信申请文件自述的问题）；③判断现有技术整体上是否给出了将该区别特征应用于最接近现有技术的**技术启示**。攻击方必须给出具体的对比文件组合与结合动机；防守方的弹药是意料不到的技术效果、克服技术偏见、以及阶段 1-H 挖出的失败尝试记录。
3. **客体（专利法第二十五条、第二条第二款；指南第二部分第九章）**：把权利要求整体读成一套业务规则或数学方法，逼防守方拿出技术问题—技术手段—技术效果三要素。
4. **公开充分（专利法第二十六条第三款）**：本领域技术人员据说明书能否实现？关键参数、阈值、终止条件、异常分支有没有交代？
5. **支持与清楚（专利法第二十六条第四款）**：独权的上位概括有没有超出说明书实际公开的范围？"所述 X"有没有在前找到明确的引入？
6. **必要技术特征（实施细则第二十三条第二款）**：把独权中任一特征拿掉，技术问题是否还能被解决？能，说明这个特征是多余的（白丢范围）；不能而独权又没写，就是缺少必要技术特征。
7. **单一性（专利法第三十一条第一款）**：各独权之间是否真的共享相同或相应的特定技术特征。

攻击奏效时按字数代价**强制顺序**响应：①**换特征**——用作用不同或耦合型特征替换被击中的特征；②**重述技术问题**——改发明内容使技术问题对应区别特征的实际作用，权利要求零字数变化；③**降抽象层级**——把机制名改写为条件/绑定，通常更短；④**加特征**——只允许加到权 2 或后续从权；向权 1 加字必须书面说明前三步为何不可行并重新通过 `CN-CLAIM-LENGTH-002`。**然后对被改动的权利要求重新跑阶段 4**，并对幸存下来的保护范围最后一次跑值不值得做。同时把每一次收窄的落脚点回写进说明书（第三十三条弹药）。

**5b. 文件包红队（整个工件）。** 只攻击权利要求不够：四文书交付包可以有完美的权利要求却仍然不能作为最终技术文书。把**组装好的四文书交付包**——权利要求书、说明书、说明书摘要和说明书附图，别的都没有——交给一个零战役上下文的全新对抗性审查者，任务是找出：四文书之间的内部矛盾（发明名称是否一致、权利要求项数与技术方案是否对得上、摘要是否准确概括且未扩大、附图说明的图号与实施方式引用是否逐号对应、附图标记与正文名称是否逐字一致）；与工件本身矛盾的验证陈述；早于最后一次编辑的印章；日期错误；不得提交的策略性评注；大而化之的现有技术定性；无依据的权利要求用语。申请人、发明人、联系电话、地址、联系人、代理机构等请求书主体字段不在本红队和本技能交付范围内。

## 阶段 6——打包

**工作副本和提交副本是分开的文件，提交副本是机械生成的。** 提交文件只包含法定内容——零括号策略笔记、零检查器分数、零"与现有技术对比"评注、零后续步骤章节。背景技术部分不做关于现有技术的绝对性承认（写"发明人已知的"，不写"没有任何系统做 X"）。用脚本从工作副本剥离提交副本，然后 diff 核对没有任何残留。

### Word 模板组装（用户要求或案件存在输出模板时）

当用户要求单一 Word 文件，或者案件根目录存在用户指定的 `输出模版.docx` 时，读取 `${CN_PATENT_CREATOR_ROOT:-${CLAUDE_PATENT_CREATOR_CN_ROOT:-${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}/vendor/claude-patent-creator-cn}}}/skills/cn-patent-application-creator/references/docx-assembly.md`，运行 `scripts/assemble_application_docx.py`。DOCX 是四类技术文书的机械组装形式，不改变“四文书”业务边界。

必须遵守以下门禁：

- 模板是版式和样式的唯一事实来源；必须复用五个分节、页眉页脚、页码、行号、页边距、权利要求自动编号和既有样式，不得另造近似版式；
- “技术领域、背景技术、发明内容、附图说明、具体实施方式”使用模板的 `Heading 1` 段落样式，并对标题文字应用 Word `Strong` 字符样式（中文界面显示为“要点”），不得只设置 `bold=True`；
- 数学表达式必须直接生成 Word 原生 OMML `m:oMath` 对象；使用 `m:f`、`m:sSub`、`m:sSup`、`m:sSubSup` 和 `m:d` 保留下标、上标、分式与括号结构。Linux、macOS 和 Windows 均不得依赖普通字符、公式截图或仅设置数学字体冒充原生公式；
- 说明书附图按 `说明书附图.md` 顺序读取当前流程生成的 PNG；摘要附图从 `说明书摘要.md` 的“摘要附图：图N。”机械确定；
- 脚本必须输出 `cn-patent-docx-assembly/v2` 报告。默认机器校验五分节、页眉序列、标题“要点”样式数量、原生公式对象数量、图片数量和 DOCX ZIP 完整性，并逐一绑定模板、四文书、全部嵌入图片和输出 DOCX 的 SHA-256；只有请求视觉检查时才记录 PDF 页数；
- **视觉检查默认关闭。** 不得仅因生成或修改了 Word 就导出 PDF、渲染 PNG、截图或逐页目视确认。只有用户明确要求检查 Word 版式、逐页截图或视觉效果时，才传入 `--visual-review`；Windows 使用 Word、Linux/macOS 使用 LibreOffice 导出 PDF，再校验 PDF 页数与 PNG 页数一致并由操作者目视复核。未请求视觉检查不构成交付缺陷。
- 未请求视觉检查时，报告写入 `render.requested=false`、`visual_review_completed=null` 和 `status=STRUCTURE_VERIFIED`；请求后写入 `render.requested=true`、`visual_review_completed=false`，待外部人工复核记录完成状态。组装后必须运行 `scripts/verify_docx_assembly.py` 复算当前输入和输出哈希；任一源文书或附图变化都使旧 DOCX 报告失效。
- 附图属于交付范围时，附图最终验证通过后必须重新组装DOCX，并运行 `cn-patent-diagram-generator/scripts/verify_drawing_docx_delivery.py`，证明DOCX报告中的逐图路径和SHA-256等于当前最终PNG；不得只凭图片数量相同沿用旧Word。用户明确要求逐页视觉检查时，视觉记录使用 `references/docx-visual-review-schema.json`。

本技能的最终交付目录固定只包含四类技术文书：

- **权利要求书**（提交副本，编号连续、引用形式合规，且按 Word 口径权利要求 1 不超过 400 字、权利要求 2 不超过 500 字、其余各项不超过 600 字——三者均为上限而非目标；公式或特殊公式变量整体计 1）；
- **说明书**（提交副本，五章节，格式按前文《说明书输出格式》）；
- **说明书摘要**（不超过 300 字）并在摘要正文或交付约定位置指定**摘要附图**；
- **说明书附图**（保留可直接编辑的 `.drawio` 母版，并从确认后的母版导出符合后续申报处理要求的 300-DPI PNG；不再生成 SVG 过程文件；母版和导出文件均须检查节点与字号比例、文字是否溢出、线条、箭头及文字是否重叠）。

用户要求单一 DOCX 或案件存在用户指定输出模板时，另交付一个包含上述四文书的合并 `.docx`；它是交付容器，不是第五类法定技术文书。

申请人、发明人、联系电话、地址、联系人、代理机构、签章、费用减缴及请求书字段不属于本技能交付范围，不得作为四文书生成完成的阻断项。序列表、生物材料保藏证明、遗传资源声明、优先权文件和第二十四条证明等条件性程序材料也不进入四文书交付目录；如技术方案触发相关事项，只在审查工作区记录缺口和提醒，不得静默认定不适用。

`technical-features.json`、`search-query.json`、`template-candidates.json`、`template-selection.json`、CNIPA 人工检索记录、范本筛选理由、`template-style-guide.json`、`composite-template-style-guide.json`、`style-brief.json`、`stage2-gate.json`、`feature-ledger.json`、`claim-architecture.json`、`claim-architecture-validation.json`、《区别特征表.md》、验证报告、哈希印章、程序时限提醒和其他策略材料均属于工作证据，保留在检索/审查工作区，不进入四文书交付目录。

**边界**：四文书交付完成不等于官方申请手续已经完备。正式递交时的请求书、主体信息、签章、费用和其他条件性文件由申报环节另行办理；本技能不得因其未提供而拒绝生成四文书，也不得把四文书包描述成官方手续完整。

## 本工作流旨在防止的失败模式

- **在用户确认范本、完成人工检索之前就动笔起草。** 写一句"检索未完成"再继续，字面合规但实质越权；阶段门的 `pending` 就是为堵这条路存在的，跳过必须带用户原话。
- **把实施例数量当成说明书形态。** `single_flow` 范本按数量拆成 N 个平行实施例，是范本学习最容易发生也最难察觉的失真。
- **手写复合风格指南。** 不在脚本输出路径上的指南没有任何机器校验，手改的数字会一路走到起草端。
- **把说明书式完整展开直接复制进独立权利要求。** 多组公式、集中符号定义和实施动作必须先做载体分工；简要性不能等到审查员指出。
- **让权利要求超过分项字数上限。** 权利要求 1 ≤400 字（`CN-CLAIM-LENGTH-002`）、权利要求 2 ≤500 字（`CN-CLAIM-LENGTH-003`）、其余各项 ≤600 字（`CN-CLAIM-LENGTH-001`）；按 Word 中文字数口径计数，完整公式或特殊公式变量整体计 1，超过上限即阻断交付。上限不是目标，不得为凑字数堆砌限定。
- **把最核心的区别特征埋进第 3 项以后的从属项，或让权利要求 2 变成另一项独立权利要求。** 权利要求 2 必须直接且仅引用权利要求 1 并承载核心保护点（`CN-CLAIM-CORE-001`、`core_protection_point`）；其他独立权利要求一律后移。
- **把实施方式的“替换连接”写成从属项的“新增连接”。** 从属项继承父项全部边，必须复算继承后的完整拓扑。
- **让权利要求、说明书和流程图各自划分步骤。** 方法步骤、判断和循环必须先在权利要求架构合同中冻结，流程图不得为了版面自行合并或改写。
- **让权利要求、说明书和附图各自持有一份技术事实副本。** 三者必须由区别特征表派生，一致性靠四向对账保证，不靠人工通读。
- 按美国节奏行事：以为可以先公开、后申请——中国的宽限期不覆盖自行发布。
- 发明明明在代码里，却相信一次交底访谈。
- 只查专利文献（致命对比文件常常是产品），或用 BigQuery 结果冒充 CNIPA 官方库检索。
- 假装抵触申请风险已被排除（它在起草时原理上检索不到）。
- 主张检索中找到的要素（它应进从属权利要求，或者死掉）。
- 把范本学习当成技术内容迁移：从范本复制限定、为贴近范本删掉必要特征，或让无效风格指南静默回退。
- 附图标记与方法步骤号共用同一数字空间，使图文一致性无法被机器核对。
- 独立权利要求缺少必要技术特征，或塞进非必要技术特征白丢范围。
- 从属权利要求多项引用后又被另一项多项从属引用。
- 为控制项数把从属方案直接删掉，而没有回落到说明书——第三十三条之下这等于永久丢弃。
- 说明书改写权利要求术语（支持缺口会在实审中暴露）。
- 附图标记用表格承载，或图上有的标记正文里找不到。
- 在线条外另建独立文本框模拟数据流或分支说明，或把文字节点串进 source→label→target 路由；关系文字必须使用 Draw.io 原生 edge label，技术关系保持一条 source→target 直连边。
- 权利要求、说明书和附图描述同一个算法的三个不同版本。
- 断言"确定性终止"却没有穷举每一个终态。
- 权利要求用语描述实现不具有的行为。
- 对已经公开的现有技术强调"赶紧申请"的紧迫性（它无法被甩在后面；先申请制只对未来的第三方申请有意义）。
- 策略评注、检查器分数、新颖性绝对化表述留在要提交给专利局的文件里。
- 审查工作区的验证报告对检查后又被编辑过的工件说"已验证"（没有内容哈希的印章是等着被发现的谎言）。
- 只攻击权利要求，从不攻击组装好的文件包。
- Word 合并文件把说明书小标题仅做手工加粗而未应用模板“要点”样式，或把公式保留为普通字符串而没有生成 `m:oMath` 原生公式对象。
- 花预算证明一项权利要求可能授权，却从不问最终得到的篱笆值不值得拥有——值不值得做在分类时提出、在检索收窄地带时重新提出、在攻击演练收窄权利要求时再次提出。
- **把"机制名称"当区别特征写进权 1。** 没有条件、绑定或参数限定的机制名称被公知常识一句话吃掉——审查员只需说"本领域技术人员知道该机制"。
- **攻击一次就往权 1 加一层限定。** 权 1 越写越长，保护范围越来越琐碎；必须先走换特征→重述问题→降层级的不加字路径。
