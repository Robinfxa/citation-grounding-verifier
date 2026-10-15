# 一手来源与读取范围

访问日期均为 2026-10-15。已通过 web search 定位，并实际打开下面的关键论文、仓库或官方指标页；不是只引用搜索摘要。网页 `main` / `stable` 是访问日视图，不伪称固定代码版本。没有安装或运行这些项目。

证据强度：**A** 为原论文定义及公开实现；**B** 为维护者官方文档；**R** 为本文针对本作业的推论/建议，不能当成来源已证明的结论。以下为八组来源，相关论文与同源仓库合并列出。

| ID | 一手来源、版本 | 实际读取 | 可借鉴与限制 |
| --- | --- | --- | --- |
| E1 | [HaluEval，EMNLP 2023](https://aclanthology.org/2023.emnlp-main.397/)、[论文 PDF](https://aclanthology.org/2023.emnlp-main.397.pdf)、[原仓库](https://github.com/RUCAIBox/HaluEval) | 论文评测设置/识别任务；仓库任务与数据说明、[MIT LICENSE](https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/LICENSE) | A：幻觉识别、人工与模型辅助构造。R：借错误设计，不直接复用整回答二分类作为三标签 claim gold；无 quote 充分性合同。 |
| E2 | [RAGTruth，ACL 2024](https://aclanthology.org/2024.acl-long.585/)、[论文 PDF](https://aclanthology.org/2024.acl-long.585.pdf)、[原仓库](https://github.com/ParticleMedia/RAGTruth) | §3.1 taxonomy、严格来源范围、`implicit_true`、仓库 `labels/start/end/label_type/split`，及 [MIT LICENSE](https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/LICENSE) | A：区分 conflict/baseless，细粒度人工 span。R：适合构造真实外部事实但上下文缺失的 U；span 幻觉标签不能未经复核直接转成原子 claim 三分类。 |
| E3 | [FActScore，EMNLP 2023](https://aclanthology.org/2023.emnlp-main.741/)、[arXiv v2，2023-10-11](https://arxiv.org/html/2305.14251v2)、[原仓库](https://github.com/shmsw25/FActScore) | 原子事实定义；§B.2 oracle individual-decision F1；Beyond factual precision；仓库 length penalty `gamma` 和 [MIT LICENSE](https://raw.githubusercontent.com/shmsw25/FActScore/main/LICENSE) | A：oracle 与系统聚合分数不同；作者明确指出 factual precision 的召回局限。R：本作业用固定 gold 分母，避免移植其传记检索流水线或长度惩罚。 |
| E4 | [ALCE，EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/)、[论文 PDF](https://aclanthology.org/2023.emnlp-main.398.pdf)、[原仓库](https://github.com/princeton-nlp/ALCE)、[eval.py](https://raw.githubusercontent.com/princeton-nlp/ALCE/main/eval.py) | §3.3 联合支持与无关引用、附录 E 部分支持限制；实现 `compute_claims`、`compute_autoais` 及其文档文本输入；[MIT LICENSE](https://raw.githubusercontent.com/princeton-nlp/ALCE/main/LICENSE) | A：引用充分性与精确率分离；正确冗余不等于无关。R：本作业应判断实际返回 quote 的联合信息，不直接照搬整段 passage 的 NLI 得分。 |
| E5 | [AIS: Measuring Attribution in Natural Language Generation Models，arXiv v2，2022-08-02](https://arxiv.org/html/2112.12870v2) | §3 standalone propositions、语境中的指代还原、两阶段标注思想 | A：先确定可理解命题，再判断 according-to-source；允许明确的多跳推理。R：原创 gold 保留条件、实体与时间，先定义可接受推理范围。期刊页访问遇 403，以上 HTML 全文可读。 |
| E6 | [ARES，NAACL 2024](https://aclanthology.org/2024.naacl-long.20.pdf)、[原仓库](https://github.com/stanford-futuredata/ARES) | §3 人工校准、训练 judge、PPI；约 150 或更多人工验证点的输入要求 | A：自动 judge 的均值不能无条件视为真值；统计保证依赖设置。R：本作业规模下直接审查 gold 和小批输出，不引入训练/PPI，不复述其保证为本项目保证。 |
| E7 | [Ragas 官方 Faithfulness 指标](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)、[维护者原文档源码](https://github.com/vibrantlabsai/ragas/blob/main/docs/concepts/metrics/available_metrics/faithfulness.md) | claims 拆分、对 context 推断、supported / total claims 的公式 | B：框架作者的可执行指标说明。R：可借鉴分解后判断的结构，但单一支持比例没有覆盖本作业的漏拆、C/U 区分和精确 quote 守门。文档 API 随版本变动，本研究不推荐引库。 |
| E8 | [SciPy 官方 bootstrap 文档，访问日 v1.18.0](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) | 重采样定义、paired 的共索引行为、percentile/basic/BCa、退化 BCa NaN 警告 | B：统计实现的官方语义。R：本作业按 case/family 配对重采样，直接重算总体比率；推荐固定 seed、10,000 次与 95% 区间，不需为此增加依赖。 |

## 许可证与复用边界

上述 E1–E4 仓库访问日根许可证均为 MIT，已打开原 LICENSE 核查。这个事实只说明仓库发布者提供的许可文本；仓库中来自其他语料、网页或知识库的内容，仍要沿具体来源追踪，不能从根许可证推导所有上游文本的再分发权。

本研究建议只复用方法与指标思想，原创 context、answer、gold，不复制代码或数据行。因此当前没有新增运行依赖，也没有迁移许可证文本的实施动作。将来若 Director 选择导入代码、模型或公共数据，应固定具体 commit/数据版本，分别核代码、权重、数据及上游来源条款；本 dossier 不代表已完成那项导入审查。

## 未作出的结论

未复现各论文得分；未验证当前包 API 兼容性；未证明某开源 evaluator 能正确处理本作业的三标签、混合条件、多段 quote 或全部技术领域。来源的论文结果只能用于其原设置。README 中的具体字段、32-case 配额、alias 对齐、分母、bootstrap 与试验流程是 R 类适配建议。
