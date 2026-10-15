# 逐断言来源忠实性：评测研究建议

研究日期：2026-10-15。状态：外部证据与可执行建议，采纳权属于父 Director。本文没有运行产品或真实模型，也不提供模拟跑分。

本次只读取项目规则、Overlay、原任务与研究约定，只写本目录；不修改产品、数据集、架构、OpenSpec、Plan，不执行 Git。项目现状对照来自 `Agent-init/PROJECT_OVERLAY.md` §0–3、§5、§8 与任务快照，未审计其他并行实施者的实现。本文无运行路径变化，local-logging-reviewer 不适用。

## 建议结论

最小但可信的交付是 **32 个原创主评测 case：8 dev / 24 test**，四类各 8 个，另设工程边界用例。对三种实现同时运行：

1. **Oracle gold-claim track**：直接将同一 case 的固定 `gold_claims[].claim_text` 交给共同的 `verify_claims(passages, claims)`；禁止重写、删项或自行补项。它隔离语义三分类与引用质量，不代表完整 `/verify` 能力。
2. **End-to-end track**：真实调用各实现的完整拆分与验证入口，使用冻结的规范化文本及预注册 aliases 作严格一对一对齐。遗漏保留为 FN，额外/重复断言保留为 FP。该轨的分数是**保守的文本对齐端到端分数**，不能声称涵盖全部正确释义。

FActScore 明确区分聚合得分与 oracle atomic facts 下的个体判断，并承认只测 factual precision 不惩罚少说事实；这支持将覆盖率独立报告。[FActScore §B.2 与局限](https://arxiv.org/html/2305.14251v2)

完整一手证据见 [sources.md](sources.md)，能力对照与复用建议见 [comparison-matrix.md](comparison-matrix.md)。以下 schema、分母、拆分和试验流程是**适配本作业的研究建议**，不是某篇论文的原样指标，也不是已采纳的产品合同。

## 标签边界先于评测

以提供的全部 context 为唯一事实范围；判断不借用模型常识补证据。

| 标签 | 必要条件 | 不满足时的处理 |
| --- | --- | --- |
| `SUPPORTED` | 一条或多条来源联合蕴含完整断言，保留实体、条件、数值、单位、范围、时态和模态 | 不能只凭高词面相似度支持 |
| `CONTRADICTED` | 来源直接反驳完整断言；例如精确值冲突、显式否定、明确反例 | “没看到”不是反证 |
| `UNSUPPORTED` | 既不充分支持，也不直接反驳；现实中可能为真 | `citations=[]` |

RAGTruth 将 conflict 与 baseless information 分开，并将现实可能正确、但引用中未提及的内容保留为严格 RAG 场景的幻觉；其 `implicit_true` 标记与本作业的外部真但未支持案例尤其相关。[RAGTruth §3.1、§3.3](https://aclanthology.org/2024.acl-long.585.pdf)

原创标注例子，不是实际模型输出：

- 来源：`When durable mode is enabled, Quartz Queue waits for a disk acknowledgement.`
- 答案：`Quartz Queue waits for a disk acknowledgement only when durable mode is enabled.`
- 金标应为 `UNSUPPORTED`：来源只给出一个方向的条件，未直接否定其他等待情形。
- 若来源另外写明 `In volatile mode, Quartz Queue also waits for a disk acknowledgement.`，该答案才有直接反例而成为 `CONTRADICTED`。

同样，`some`→`all`、`may`→`always` 不应自动标为矛盾；需要来源存在直接反证。空值表示未知也不应自动改成否定。

基础分数集应使用来源内部一致、可清晰判定的 case。上下文互相冲突、模糊模态、需领域常识或非平凡数学证明的输入可作独立诊断集；父 Director 先定义冲突政策，再将其纳入计分，避免研究者替产品拍板。

## 主数据集及拆分

| 主覆盖类 | Dev | Test | 原创设计重点 |
| --- | ---: | ---: | --- |
| 完全支持 | 2 | 6 | 含正确释义、条件、例外、代词消解、一个句子多个事实 |
| 细微失真 | 2 | 6 | 数字边界、单位、否定、实体/版本/条件交换；不强求全部为 C |
| 外部未支持 | 2 | 6 | 可信但上下文缺失的默认值、安全性质、性能、原因、持久性 |
| 多段综合 | 2 | 6 | 单个必要事实需要至少两段联合；混入遗漏一段会改变结果的 case |
| 合计 | 8 | 24 | 主覆盖标签互斥，细粒度标签可以重叠 |

四类平衡不等于三分类平衡。冻结前统计每个 split 的 S/C/U 断言数；建议 test 每类标签至少 12 个可判定断言、每 case 2–4 条金标，避免全支持案例使 S 占绝大多数。达不到时调整案例内容，不能在跑分后重采样标签来美化结果。这里的数量是工程可执行的建议，不是统计充分性保证。

每个 case 采用独立、短小、原创的技术说明，优先用虚构产品名和完整的局部规则，标明 `original_fixture`。它们测来源忠实性，不冒充真实产品文档或自然模型生成分布。可借用公开论文的错误类别，避免复制其人物、措辞、来源段落、答案或金标。公开数据已经长期可见；原创内容降低逐字记忆与再分发的负担，但不证明零污染或真实世界泛化。

32 个 case 的创作配方可在四类中分别安排八个独立 mini-context：

- 支持类：同义释义、正确边界、正确条件、规则加例外、代词还原、列表展开、单位关系已在来源定义、一个句子两事实。
- 失真类：包含边界的 off-by-one、单位替换、显式否定反转、角色交换、版本范围错误、条件倒置、量词增强、错误默认值。
- 未支持类：加密、保留周期、跨主机保证、容量、性能外推、因果外推、null→否定、局部→普遍。
- 多段类：别名解析、两项共同前提、版本与开关、已定义的简单算术、两个节点的比较、跨段例外、范围与限制、两段分别给出必要条件。

“多段”必须是同一断言需要多段，而不是答案里两条独立断言恰好各引一段。至少保留支持和不成立的综合例子，防止“看到两个 passage 就支持”的捷径。

同源模板、同段上下文的变体、仅改数字的正负样本共用 `family_id`，整个 family 进入同一 split。不要将一对仅差一个 token 的案例拆到 dev/test。若 32 个 case 都独立，bootstrap 单位就是 case；若它们有共享 family，独立样本量按 family 计算。

空 context、纯致谢、空答案、坏 JSON、非法 index、伪造 quote、provider 失败/超时另设工程测试。零金标的有效 case 计入请求/案例成功率，但不向 claim 级分母添加虚构断言，也不因 `0/0` 获得满分。纯工程故障注入不得与自然质量得分混为一个榜单。

## 最小评测 schema

主数据行保留以下字段即可；这是数据建议，不要求改公开 API：

```json
{
  "id": "original-cache-01",
  "family_id": "original-cache-01",
  "split": "test",
  "category": "subtle_distortion",
  "tags": ["numeric", "negation", "compound_sentence"],
  "provenance": {"kind": "original_fixture"},
  "context_passages": [
    "Nimbus Cache stores entries for exactly 40 seconds. Nimbus Cache does not persist entries to disk."
  ],
  "generated_answer": "Nimbus Cache stores entries for 41 seconds and persists entries to disk.",
  "gold_claims": [
    {
      "id": "c1",
      "claim_text": "Nimbus Cache stores entries for 41 seconds.",
      "aliases": [],
      "verdict": "CONTRADICTED",
      "evidence_sets": [[
        {"index": 0, "quote": "Nimbus Cache stores entries for exactly 40 seconds."}
      ]],
      "rationale": "The source gives the exact lifetime as 40 seconds."
    },
    {
      "id": "c2",
      "claim_text": "Nimbus Cache persists entries to disk.",
      "aliases": [],
      "verdict": "CONTRADICTED",
      "evidence_sets": [[
        {"index": 0, "quote": "Nimbus Cache does not persist entries to disk."}
      ]],
      "rationale": "The source explicitly rules out disk persistence."
    }
  ]
}
```

这个 JSON 只是展示格式，尚未作为产品数据集或接受度样例交付。

`evidence_sets` 外层是 OR：存在任一充分证据组即可；内层是 AND：该组的每条片段共同提供必要信息。`UNSUPPORTED` 的金标证据组为空数组。需要多段的金标组必须含全部必要 passage 的精确引文。可选添加答案锚点 `answer_spans` 与证据 offsets，但固定为原字符串的半开区间，别让 offsets 产生另一套文本真相。

金标作者先按答案抽出独立可判断命题，再逐条核来源。对至少全部 test 金标做一次独立复核，复核者不看各系统输出；若没有独立人类标注，只能如实报告为作者编写、代理辅助复核，不能声称人工一致性研究。AIS 强调先确定语境中可理解的命题，再判断归因，支持保留指代、时间和范围。[AIS §3–4](https://arxiv.org/html/2112.12870v2)

## 严格对齐与已知偏差

最小 scorer 可自动复现，且不需要新增 LLM judge：

1. 冻结规范化函数与每条金标的 `claim_text + aliases`。仅采用明确不改义的空白规则；不要删否定、数字、单位、比较符号、条件词或代码标识的大小写。quote 守门始终对原始 passage 做精确子串检查，不使用这套 claim 规范化。
2. 每 case 检查各 gold 的规范化 alias 集合互不重叠。alias 在查看 test 输出前定义；把测试输出补成 alias 后原表重跑会泄漏。
3. 仅在预测文本与某 gold 的规范化文本/alias 相等时建立边。匹配过程不读取 predicted verdict、引文、gold verdict 来挑选有利边。
4. 每 gold 至多匹配一次，每条预测至多匹配一次。重复输出不能增加召回，仍占预测数。复合句不能仅因含某 gold 的关键词就获得一条或多条完整命中的奖励。
5. 未匹配 gold 为 FN；未匹配、重复、额外、变义预测为 FP。词面/embedding 模糊候选仅用于人工查错，不进入 headline。

这不是语义拆分的完整测量：正确但未预注册的释义、合法粒度差异可能被低估。报告严格对齐结果时必须保留这一限制；oracle 轨消除拆分和对齐的影响。若预算允许，对所有未匹配项做盲化人工次级复核，单列语义复核结果，不能静默覆盖主分数。任何 LLM judge 也只能给候选意见，不能与被测模型共用提示后自证正确。

一个反例足以解释为何不能用词面最佳配对：gold 为“写入上限为 40”，预测为“写入上限为 41”，即使二者都输出 `CONTRADICTED`，命题已改变，不能因相似度高、标签恰好相同而算正确。

## 指标与分母

定义所有已尝试 case 的金标总数为 `G`，最终成功报告中的全部预测断言数为 `P`，严格文本匹配对数为 `M`，其中 verdict 正确的匹配数为 `T`，再满足引文要求的数为 `Q`。`P` 包括重复、额外和复合预测。整次请求错误时没有最终预测，但该 case 的全部 gold 仍在 `G`；不可丢弃失败 case。

| 指标 | 计算 | 解读与边界 |
| --- | --- | --- |
| 严格拆分 precision/recall/F1 | `M/P`, `M/G`, `2M/(P+G)` | 与 verdict 无关；这是文本/alias 覆盖的保守代理 |
| End-to-end verdict precision/recall/F1 | `T/P`, `T/G`, `2T/(P+G)` | 标签错误的匹配同时损失一项精确率与召回率 |
| Strict evidence F1 | `2Q/(P+G)` | 正确命题、verdict、合法且充分的引文；U 必须无引文 |
| Oracle macro-F1 | 对 S/C/U 分别算 P/R/F1，再取三类均值 | 所有 gold 输入都计入；错误/缺失预测放独立 `ERROR` 列并作该 gold 的 FN |
| Oracle accuracy | 正确 verdict 数 / 全部 oracle gold 数 | 同时给三类混淆矩阵及各类样本数；不将 ERROR 当第四语义类 |
| Gold 非 U 的引用充分率 | 正确匹配、正确 verdict 且充分引用的非 U 数 / 全部非 U gold 数 | 漏拆、错判、错误请求均为分子 0，不能靠少输出提高 |
| 预测引用充分率 | 证据联合足以支持/反驳其完整命题的非 U 预测数 / 全部非 U 预测数 | 诊断指标；必须伴随 gold 分母指标，否则可漏事实刷高 |
| 引文精确率 | 合法且对该断言有实际支持/反驳贡献的引文附件数 / 全部引文附件数 | 每断言内重复 `(index, quote)` 去重；与联合充分性分开 |
| 字面引用合法率 | index 合法且非空精确子串的引文数 / 全部引文数 | 守门可能使最终结果恒为 100%；不代表语义质量 |
| Case exact | 全覆盖、无额外断言、标签和引文均正确的案例数 / 全部已尝试有效案例数 | 有效零事实答案要求成功返回空 claims；请求失败计 0 |

所有表格一起给出原始分子/分母。分母为零时输出 `null / not_applicable` 及计数，不能默认为 1。整套主集 `G>0` 且系统全失败时，召回和两种 F1 为 0，precision 因无输出可为 null；这些 case 仍计入请求失败率。某 split 缺某标签时不要把缺失类当满分，先修数据覆盖，或者明确该 macro-F1 不可比。

还应报告 `successes / attempted_requests`、错误分类计数、首次模型输出 schema/quote 失败数、修复调用次数、最终失败数。把 provider 失败或 quote 守门失败改写成 U 会污染语义分数；“成功请求上的分数”只能作为附加诊断，不能替代所有尝试上的主分数。

## 引文判分要看 quote，不只看 passage index

ALCE 的引用召回检查联合引用是否充分，引用精确率检查无关引用；二者不同。其主要自动指标用 NLI 读取被引用的 passage，并公开讨论部分支持与冗余引文的局限。[ALCE §3.3、附录 E](https://aclanthology.org/2023.emnlp-main.398.pdf) 本作业实际返回的是精确 quote，所以建议：

- 先机械核 index、非空精确子串、S/C 必须有引文、U 必须无引文。
- 语义充分性只看输出 quote 联合包含的信息；不能因为对应整段 passage 有所需条件，就给删掉条件的短 quote 满分。
- `CONTRADICTED` 引文应直接反驳原命题；不能只找与主题相同的另一句。
- 多段证据以完整组判断，缺一条必要证据就不充分。
- 金标 alternatives 定义最小充分组，但合法输出可以比最小组更长。主自动结果若只认可预注册 quote/span，应标为保守的 gold-evidence match；不同但充分的精确引用交人工次级复核，不能宣称 span exact match 等价于语义正确。
- 正确而冗余的引用不必当错；无关引用降低精确率。可附加每断言引用字符数，暴露全文引用策略，但无需发明“最短引用”最优指标。

## 三种实现的公平条件

| 条件 | 最小可执行规则 |
| --- | --- |
| 相同输入 | 同一原始 passages、answer、顺序、split、gold 和 evaluator；禁止模型外部检索补事实 |
| 非 LLM baseline | 句子拆分加词面检索/数字与否定规则即可；阈值只在 dev 调整，真实记录其限制；不要故意构造弱 baseline |
| Minimal LLM | 固定一个简短单次调用 prompt；共享输出 schema 和最终确定性守门；不含 test 示例 |
| Optimized LLM | 与 minimal 使用同一 provider/model snapshot 和采样配置，允许不同分解/校验/重试策略；额外调用全部计入时间、tokens、费用 |
| 等工作量的解释 | 比较三种完整系统时无需强制相同调用数，但不能把额外计算收益说成纯 prompt 收益；需要此结论时做同模型、同预算消融 |
| 失败政策 | 相同网络 timeout 与基础 transport retry；优化版内容修复属于优化算法，单列且计费；禁止反复重跑直到成功再选最好结果 |
| 输出守门 | 三者都遵守相同 index/quote/schema 不变量；最小版失败也显式记录，不能给其额外豁免或给优化版静默修复 |
| Oracle adapter | 固定 claim 列表进入同一 `verify_claims` seam，保持一条输入一条结果；该 seam 不要求新增公开 HTTP API |
| 顺序与缓存 | 固定 seed，轮转/随机系统执行顺序；明确缓存、冷/热启动及并发；三者不共用答案缓存冒充调用 |
| 时间与费用 | 记录每 case 从消费者入口到最终结果的 wall time，包含分解、守门、重试；tokens 取 provider usage；未知值为 null，不填 0 |

报告 median 与 p95 latency，并给样本数；24 个 test 的 p95 很不稳定。失败也计入消耗，超时按实际等候时长报告并标为超时，不只保留快的成功调用。成本按报告日期的实际价格与 usage 估计，价格来源/快照随报告固定；供应商未回 usage 的失败要单列未知消耗。没有项目凭据时只报告真实可运行的非 LLM 与工程检查，将 LLM 指标写 `NOT_RUN`，不可用 scripted provider 代填真实质量、时延或成本。

若预算足够做三次完整 live repetition，保留每次结果，按 case 聚合；重复调用不增加独立 case 数。最低交付可只做一次完整质量运行并明确限制；不要把模型随机性与测试样本不确定性混成一个 CI。

## Bootstrap CI

对主 test 集使用 **配对的 case/family cluster bootstrap**：固定 seed（例如 20261015），有放回抽样同样数量的 case 或独立 family，每次用同一抽样索引重算三个系统的总分子/分母，建议 10,000 次。对 ratio/F1 必须重算，不能先平均各 case 的 F1 再称 micro-F1。

输出各主分数与 `optimized - minimal` 的配对差值的 95% percentile 区间，并写明重采样单位、seed、次数、方法。相同 case 内的多个 claims、多个模型输出和重复运行不是独立样本。SciPy 官方文档说明 `paired=True` 使用共同索引，也记录 BCa 在退化数据上可能出现 NaN；可借其定义，不需要因此引入 SciPy 依赖。[SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)

上述 percentile 选择是本作业的简化建议，不是宣称比 BCa 普遍更好。只有 24 test 的区间很粗；全正确/全失败时重采样可能退化成零宽区间，要标记“不提供有信息量的不确定性估计”，不能宣称零不确定性。这里的区间仅描述这个人为设计分布的样本敏感性，不覆盖标注偏差、模板偏差、污染或真实部署分布。

ARES 用校准的人类标注与 prediction-powered inference 处理 judge 偏差；其评估设置需要约 150 个或更多人工验证点，不能把其保证套在 20–32 个自建 case 上。[ARES §3](https://aclanthology.org/2024.naacl-long.20.pdf) 本作业优先直接审查小数据集，不增加训练 judge 与 PPI 工程。

## Eval-driven hill climbing

1. 冻结数据版本、按 family 的 split、alias、金标证据和主指标；保留内容 hash。推荐主比较为 strict evidence F1，辅以 oracle macro-F1 和请求成功率，成本作预算与并列结果的决策依据。
2. 先跑三种实现的 dev，保存真实逐 case 错误：漏断言、复合断言、S/C/U 混淆、数字/条件失真、quote 字面错误、quote 不充分、provider/schema 失败。
3. 每轮只针对一个可复现错误假设调整，说明期望影响哪个指标。例如先修漏拆，再比较证据分组提示，最后评估有限内容修复；可做去掉各优化项的 dev 消融，确认额外成本是否换来可重复收益。
4. 选定优化版本后冻结 prompt、模型、配置、evaluator，统一运行 test。不能观察 test 错误后继续调 prompt 并仍称同一 test 为未见测试集。
5. 若 test 暴露真实金标错误，保留旧报告、修订数据版本并让三者全部重跑；如按 test 表现做过系统选择，后续改进需要新 holdout。实验事实写进现有报告/验证位置，不另建工作流账本。

Ragas 官方 faithfulness 定义是已提取断言中可由上下文支持的比例，适合诊断，但不能替代本作业对拆分遗漏、三类标签和 quote 合同的验收。[Ragas Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)

## 报告最小内容及边界

每个系统两轨分开列原始计数、严格拆分 F1、end-to-end verdict F1、strict evidence F1、oracle 三类宏 F1、gold 非 U 引文充分率、引文精确率、成功/尝试数，以及时延、tokens、费用和 CI。附 3–5 个真实失败输出及其金标解释，特别展示高词面相似的数值/否定错误和多段缺证据。

不要用单一“faithfulness”百分比掩盖任务差异：HaluEval 主要是回答级幻觉识别，RAGTruth 有 span 级标注，FActScore 是原子事实支持比例，ALCE 测生成文本的引用质量。它们适合借鉴局部思想，不能直接拼接 label 或横向比较已发表分数。[HaluEval](https://aclanthology.org/2023.emnlp-main.397/)、[RAGTruth](https://aclanthology.org/2024.acl-long.585/)、[FActScore](https://aclanthology.org/2023.emnlp-main.741/)、[ALCE](https://aclanthology.org/2023.emnlp-main.398/)

剩余局限须直接披露：自建小样本、技术领域/语言范围、原创合成答案与真实生成的分布差异、严格 alias/quote 对齐低估正确释义与替代引文、标注者身份与未决项、模型版本和随机性、未实测的 live provider。研究本身不建立三种系统谁更好的结论。
