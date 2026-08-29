# 中国发明专利实体审查规则（CN v2）

本文件是 [cn-review-contract-v2.json](cn-review-contract-v2.json) 中 17 个实体核心维度、4 个有效日/优先权/宽限期维度及 3 个条件性特殊领域维度的阅读索引。稳定 ID、法源定位和状态要求以 JSON 为唯一机器解释来源。

## 实体审查边界

- `novelty`：逐项权利要求只能与一项单独的现有技术技术方案比较；不得拼接文献或同一文献中相互独立的方案。
- `inventiveness`：保留最接近现有技术、区别特征、区别特征的技术效果、实际技术问题、技术启示和反事后分析记录。
- `claim_clarity`、`claim_support` 与 `essential_features` 是独立维度；结构命中不等同于语义法律结论。
- `priority_entitlement_effective_date`、`claim_level_priority`、`partial_multiple_priority` 与 `article_24_grace_period` 不能折叠为笼统的优先权形式问题。
- `computer_and_ai`、`chemical_and_biotech`、`traditional_chinese_medicine` 即使不适用，也必须有充分适用性证据形成 `NOT_APPLICABLE`，或作为明确 gap 保持审查不完整。

所有实体结论均为咨询性输出，不构成授权、可申报或专业确认。
