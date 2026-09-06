# 范本 IPC 判定与加权选择规范

本规范用于在中国发明专利起草阶段选择撰写范本。目标是避免只凭标题、摘要或申请人知名度挑选范本，使范本与目标技术方案在国际专利分类（IPC）上也具有可核对的接近关系。

## 一、目标 IPC 必须先确定

`technical-features.json` 必须显式填写经人工判断的 `ipc_codes`：

```json
{
  "technical_problem": "……",
  "technical_solution": "……",
  "ipc_codes": ["G06F11/36"],
  "cpc_codes": ["G06F11/36"]
}
```

`generate_search_query.py` 会在 `search-query.json` 中生成：

```json
{
  "target_ipc": {
    "status": "determined",
    "ipc_codes": ["G06F11/36"],
    "suggested_ipc_codes": ["G06F"],
    "source": "technical_features_explicit"
  }
}
```

只有显式填写的 IPC 进入范本相似度计算。关键词映射产生的宽分类仅放入 `suggested_ipc_codes`，防止宽泛的 `G06F`、`H04L` 把无关候选错误评为完全匹配。

若未显式填写，状态为 `suggested` 或 `unresolved`，`rank_template_candidates.py` 必须拒绝继续。

## 二、候选清单

候选文件使用 `cn-patent-template-candidates/v1`：

```json
{
  "schema_id": "cn-patent-template-candidates/v1",
  "searched_at": "2026-08-27",
  "database": "Google Patents",
  "candidates": [
    {
      "publication_number": "CN104978263B",
      "title": "一种移动端应用程序测试方法及系统",
      "assignee": "腾讯科技（深圳）有限公司",
      "search_rank": 7,
      "technical_relevance_score": 0.9,
      "technical_relevance_reason": "同属移动端应用自动化测试，并包含测试任务、设备故障处理和结果校验"
    }
  ]
}
```

`technical_relevance_score` 由起草者基于技术问题、核心机制、系统边界和文书完整度评定，不得只把搜索排名换算为相关性。

## 三、候选 IPC 来源顺序

`rank_template_candidates.py` 对每个候选按以下顺序取 IPC：

1. **EPO OPS**：通过 `--epo-provider-command` 或 `CN_PATENT_EPO_PROVIDER_COMMAND` 调用独立 provider；provider 接收公开号参数并输出 `{"ipc_codes": [...]}`，新项目不得反向 import 其他仓库；
2. **分类缓存**：例如先前 EPO/BigQuery 查询结果，必须登记 `source`；
3. **候选输入**：候选 JSON 已携带 `ipc_codes` 和 `classification_source`；
4. 仍无 IPC：标记 `unresolved`，不得入选。

EPO OPS 需要：

```text
EPO_OPS_KEY
EPO_OPS_SECRET
```

不得记录、打印或提交真实凭据。EPO 失败时报告必须保留 `unavailable`、`not_found` 或 `error` 状态及原因，不能静默改用其他来源。

## 四、IPC 相似度

针对目标 IPC 与候选 IPC 的所有组合取最高值：

| 层级 | 分值 |
|---|---:|
| 完整分类号相同 | 1.00 |
| 同主组 | 0.85 |
| 同小类（如 G06F） | 0.65 |
| 同大类（如 G06） | 0.45 |
| 同部（如 G） | 0.20 |
| 无共同层级 | 0.00 |

输入中的空格、版本括号和分隔符会先规范化，例如 `G06F 11/36 (2006.01)` 归一为 `G06F11/36`。

## 五、综合评分

默认：

```text
综合得分 = 技术相关性 × 0.65 + IPC相似度 × 0.35
```

IPC 权重可以按案件调整，但必须大于零且技术相关性权重与 IPC 权重之和为 1。

运行：

```bash
python skills/cn-patent-application-creator/scripts/rank_template_candidates.py \
  --search-query "01-检索/search-query.json" \
  --candidates "01-检索/template-candidates.json" \
  --classification-cache "01-检索/ipc-cache.json" \
  --ipc-weight 0.35 \
  --output "01-检索/template-selection.json"
```

人工选择不同于加权最高候选时：

```bash
python skills/cn-patent-application-creator/scripts/rank_template_candidates.py \
  ... \
  --selected "CN……" \
  --selection-reason "虽然IPC仅同小类，但说明书的系统时序结构更接近本案"
```

## 六、阶段门

新案件使用 `cn-patent-stage2-gate/v2`，在 `template_selection` 中登记：

```json
{
  "status": "confirmed",
  "style_guides": ["01-检索/范本提取/CN……/template-style-guide.json"],
  "search_query_path": "01-检索/search-query.json",
  "candidate_manifest_path": "01-检索/template-candidates.json",
  "selection_report_path": "01-检索/template-selection.json",
  "user_authorization": {
    "user_quote": "……",
    "granted_at": "YYYY-MM-DD"
  }
}
```

阶段门核对：

- 目标 IPC 已确定且非空；
- IPC 相似度具有正权重；
- 选定候选取得逐篇 IPC；
- EPO OPS 是第一尝试来源；
- 降级来源及原因可追溯；
- 搜索清单和候选清单哈希未变化；
- 选定公开号与 `template-style-guide.json` 一致；
- 偏离推荐候选时有明确理由。
