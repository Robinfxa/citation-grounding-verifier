# 能力对照与借鉴建议

本表只给父 Director 提供证据，不记录采纳决定。现状只对照原任务与 Overlay；并行代码没有在本研究范围内审计。

三态词汇：`已 borrow` 需要有可核实的项目采纳记录；`精简版漏算法` 需要核实项目已复用部分方案但缺关键算法；`未 borrow` 表示本研究没有核实已采纳。不能因项目目标与论文相似就声称已借鉴。当前没有可核实的算法采纳记录，因此下面统一保守标为未 borrow；已有需求/不变量单独说明。

| 候选能力/来源 | 现有任务或规则 | 借鉴状态 | 最小建议 | 工程量/收益/风险 |
| --- | --- | --- | --- | --- |
| 原子事实与 oracle 个体判断，E3 | 已要求逐断言验证、不得漏 gold | 未 borrow | 固定 gold-claim 轨独立于端到端轨 | 低；定位判定和拆分问题；不能把 oracle 分数当 API 分数 |
| 来源范围与 conflict/baseless，E2/E5 | 已定义 S/C/U 与 context-only | 未 borrow | 写清条件倒置、量词增强、现实为真但无证据的标注例子 | 低；降低金标误标；复杂语义仍需审查 |
| 覆盖与额外断言 | Overlay 已禁止漏 gold 算正确 | 未 borrow | 严格 aliases 一对一，漏项 FN，额外/重复 FP；同时报告 oracle | 低；防空输出/少拆刷高；低估未注册释义 |
| 引用充分性/精确率分离，E4 | 已要求 exact quote；字面存在不等于蕴含 | 未 borrow | quote 联合充分性加引文相关性两个指标 | 中；发现“引用存在但不证明”；exact gold span 会低估替代证据 |
| 公开幻觉语料，E1/E2/E3 | 任务允许改编或原创 | 未 borrow | 借覆盖类别，优先原创虚构技术说明和答案 | 中；避免照搬与便于控标签；合成分布可能过于简单 |
| 全回答幻觉 accuracy，E1 | API 是逐断言三标签 | 未 borrow | 只保留 case-exact 辅助指标，不用其替代 claim metrics | 低；便于读报告；单个错误会把整 case 判失败 |
| Ragas supported/total，E7 | 需要同时比较拆分、判定、引用 | 未 borrow | 可作诊断思想，不作为唯一 headline，不引库 | 低；结构清楚；提取遗漏可隐藏错误，且不区分 C/U |
| ALCE 整段 AutoAIS，E4 | 本任务返回特定 quote | 未 borrow | 不直接移植；最小主评分用预注册证据组，次级审查替代引用 | 低至中；可复现；不能把整段 entailment 说成输出 quote 充分 |
| ARES finetuned judge/PPI，E6 | 只有至少 20 case 的作业规模 | 未 borrow | 暂不引入；保留人工/独立复核和明确 CI 范围 | 节省大量工程；不享有论文的 PPI 保证 |
| 配对 bootstrap，E8 | Overlay 已要求 CI | 未 borrow | 以 case/family 为簇、共享抽样索引、重算计数比率及差值 | 低；展现小样本敏感性；不能覆盖标注和分布偏差 |

建议父 Director 优先将双轨、固定分母、quote 联合充分性、family split、错误透明计数写进既有评测合同。32-case 内容与 JSONL 由后续有数据写权的 owner 编写，本研究未创建产品数据。严格 alias/证据组的局限应在报告中明确，而不是为追求自动化将它们改名为完整语义准确率。

暂不建议新增 evaluator 框架、训练模型、检索库、PPI 或额外 LLM judge 依赖。它们在本规模下增加不透明性；本作业的独立金标与小型 scorer 已能检验最重要缺口。是否采纳这些建议、如何形成最终 API 与 OpenSpec 合同，仍由父 Director 决定。
