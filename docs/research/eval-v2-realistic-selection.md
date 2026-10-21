# 真实来源数据选择与交付记录

本轮交付是许可明确的真实文档主集，加一个可私有重建的 RAGTruth 真实自然回复辅助集。主集不是 RAGTruth、HaluEval 或 FActScore 数据的改名版本，也不把 AI 根据文档新写的答案称为已记录的真实模型输出。数据作者未读取保存的 verifier 预测，未修改 prompt、scorer、alias 规则或运行产品 benchmark。

## 主集候选与来源

`datasets/v2/realistic-draft/main-candidate.jsonl` 是可由现有消费者严格加载的 72 条候选，邻接 manifest 保留完整来源文件、许可文件和原文连续 Unicode 映射。数据 SHA256 为 `d2c809677180d5400dcb23a0d7d322198b2cea057e42427410e5a77fd779aee5`，manifest SHA256 为 `9a67ff72f54fcb1cb6aaaf0744bcd36dce7a0357ad52b9ddfb8ce492db5f35d8`，统一 annotation_version 为 `v2-realistic-candidate-1`。最终提升到默认数据集及实际模型测量由父 owner 串行处理。

| 部分 | cases | families | claims | 来源组件 |
|---|---:|---:|---:|---|
| 继承 pilot dev | 12 | 12 | 126 | 原 `datasets/v2/pilot.jsonl` |
| 新增 dev | 12 | 12 | 132 | `dev-revised-2.jsonl` |
| test 第一组 | 24 | 12 | 210 | `test-first24-revised-2.jsonl` |
| test 第二组 | 24 | 12 | 200 | `test-second24-revised-1.jsonl` |
| 合计 | 72 | 48 | 668 | 24 dev / 48 test |

组装仅在派生候选中统一 `provenance.annotation_version`；所有其他字段与上述组件精确相等，包含 pilot 的 126 条 gold、答案和上下文。原 pilot/v1 以及历史草稿、盲包、盲锁均保留。为使相邻 manifest 的路径安全且可离线加载，pilot 的 12 个 raw 和 5 个完整许可文件按原字节复制到 `pilot-import/`，原文件未改。来源组件、case/family/split/origin/category、原版本与 hashes 的映射在相邻 metadata；完整测试内容没有回传 prompt optimizer。

| 项目 | source-topic families | 固定 revision | 保留许可 |
|---|---:|---|---|
| CPython 3.13.0 文档 | 18 | `60403a5409ff2c3f3b07dd2ca91a7a3e096839c7` | Python 完整 LICENSE 与文档许可/历史 |
| Rust Reference | 9 | `2dafab96d919d6ab2884488e970bf95610ff83eb` | MIT，另保留 Apache 2.0 原件 |
| PostgreSQL pilot 文档 | 3 | `d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e` | PostgreSQL 完整 COPYRIGHT |
| pytest 8.3.3 文档 | 9 | `d0f136fe64f9374f18a04562305b178fb380d1ec` | MIT |
| curl 8.10.1 选项文档 | 9 | `7eb8c048470ed2cc14dca75be9c1cdae7ac8498b` | curl COPYING，文件内 author/SPDX 保留 |

83 个实际 source 文件的 URL、revision、raw/license SHA256 在 manifest，原文只选择和分段，不清洗、改写或为制造证据而拼接。独立来源 reviewer 对本轮 94 个来源/许可文件、90 个固定上游 URL，以及 17 个 pilot 副本做了字节核查；候选的 273 个 passage 映射和四组件组装也通过真实严格消费者检查。完整署名与路径在候选目录的 `NOTICE`。该检查不把来源许可文本的存在误作每个语义标签的证明。

## 内容与难度口径

主集的 48 条 `generated_from_real_source` 是 AI 作者基于真实文档新写、未受控插错的答案；24 条是明确记录 baseline 和 mutation 的受控变体。主集 `natural_response` 为 0。非注错答案中独审发现的真实遗漏条件没有通过改答案消除：45 条全 S，3 条含 U；受控答案 24 条均含 C 或 U。总计 45 条全 S 长答案，避免把“每个答案必有错”变成采样暗示。

| case 类别 | 数量 |
|---|---:|
| supported | 34 |
| synthesis | 11 |
| subtle_distortion | 9 |
| extrinsic | 18 |

gold 总量为 S 598、C 47、U 23；含 C 的 family 为 21，含 U 的 family 为 15。单 case 分类用于采样：含 U 优先归 extrinsic，否则含 C 归 subtle_distortion，正确答案保留 supported/synthesis；混合标签仍按 claim 逐条统计，不能从 case 类别推出所有断言同类。S 占比较高是实际观察结果，没有为平衡标签把自然生成答案改错。

72 条 context 均约 976–3990 estimated tokens，估计方法是 Unicode 字符数除以四，不是 tokenizer 或 provider 用量。答案正文为 74–135 个空白分词，gold 数量分布为 8 条×29 cases、9×19、10×9、11×8、12×5、13×1、14×1；两条超过 12 的偏离透明保留。答案保留自然段、并列、指代、条件与实际使用问题，没有把全部改成八个独立短句。完整相关章节、示例和同页干扰可保留；“未被答案引用”本身不等于无关 padding。

新增 60 条都有实际 scope/条件边界，必须组合不同 passage 才能推出结论的实质链仅 2 条；继承 pilot 另有 2 条，总计 4。A 覆盖的 dev12/首24 实质链为 0，B 覆盖的次24 为 2。不能把补标题绑定、多个引文、并行列举或相邻段分块自动算作实质跨段。该难度分类来自分组独立审查和明确口径，不是测得的模型难度，更不声称三分之一 case 必须跨段。

新增 60 条使用可见输入适配 `Question: {question}\n\nAnswer: {answer}`，原问句与未加前缀答案/hash 保存在组件 metadata。问句是 AI 作者提出的任务，不是生产用户日志，也不是 context 证据；问句没有作为额外依据的事实历史。gold answer_anchor 指向完整适配字符串。原 pilot 输入按授权原样保留。实体、动作、条件和被断言关系仍必须由答案和引用覆盖，不能靠 question 暗示补成 S。

## 盲审、修订与分离

作者先封存只含 context、answer、origin 的盲包和单独 sealed gold；A/B 从盲包独立抽取完整断言并锁定标签和充分引文，锁定后才与作者 gold 比较。盲审有更细的原子化数量，不等于机械照抄新增事实数；遗漏、混合断言、条件缺失、相近 API 错绑与主体引用不足均按单项裁决。新增 dev 经过两版修订，test 首组经过两版、次组一版；仅六条受控首组答案有公开记录的九个句号插入，所有非注错答案及全部 context 未改。原独立盲记录与锁保持。

旧 pilot 的原 handoff metadata 保留了当时的 pending；后续 `reports/eval-v2/annotation-review/affected-review.{json,md}` 接受了 81 条受影响 gold，并对 45 条未变项逐字段精确复用。候选 sidecar 绑定该较晚证据，不修改旧快照。新增 dev132、首组 test210、次组 test200 的受影响复核都已接受，标注未决请求为 0。审查者为非作者 AI，未冒充 human signoff，亦不等同于 verifier 准确率。

新增 60 条另有公开证据旁路 `datasets/v2/realistic-draft/review-evidence/`，不修改已接受 candidate 或 metadata hash。三份真实原始盲判断共 145+275+245=665 项，安全检查后按原字复制；锁只投影去掉明确列出的私有输入路径/路由字段。实际受影响接受与对照记录、作者最终字段差异、逐 issue 裁决投影和原 blind 输入重建规则一并归档。`publication-manifest.json` 分别记录每件的 original SHA、公开号 SHA、投影规则和省略字段；身份复制才会两 hash 相同，修改后的投影不冒称原锁。该档案只含许可文档主集，不混入新闻/自然回复的私有盲注。

family 口径是原文档/API/主题簇；相关选项、来源版本和每个回答变体固定同 split。最终 manifest 的 family、source_id、source URL、raw hash、exact passage hash 跨 split 交集均为 0。它没有把同项目不同主题伪称项目独立：CPython、Rust、pytest、curl 同时存在于 dev/test，通用编程概念与文风仍相关。

词面审计以每 family 首个 context 版本、至少 20 词的真实段落、5-word shingles 的 Jaccard≥0.5，或 containment≥0.8 且共享≥20 个 shingles 检出 12 对；独立 reviewer 逐对读原串并复算，均为 pytest session-output boilerplate，没有在这些命中中发现实质说明或答案命题复制。该 reviewer 在同一窄人口补做较短段落/3gram/连续八词检查，另见两个失败 summary 模板，同样无实质复制。最终 72 条 context 数组与受审输入全部相同，因此该结论可绑定最终输入；没有为让计数变零而删除真实来源头。准确表述是“在指定词面阈值及已审命中中未发现实质复制”，不能据此证明全库语义独立。

技术文档集中、公开训练暴露、相近概念、S 标签偏重、仅 4 条必须跨段，以及 AI 作者与 AI reviewer 的共同模型族偏差仍是限制。

## RAGTruth：真实回复的独立辅助层

实际使用 [ParticleMedia/RAGTruth 固定源码](https://github.com/ParticleMedia/RAGTruth/tree/c103204b9ce28d6bbad859304bf30de72b8ed8fe) 的 `dataset/response.jsonl` 和 `source_info.jsonl`。仓库确有 [MIT LICENSE](https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/LICENSE)，这不被解释为给全部上游新闻、MARCO 或 Yelp 文本授予完整转载权。可完整离线打包的主集因此采用上表许可文档；RAGTruth 完整 source/response 保留在私有下载工作区，公开仅 metadata、原 span 类型/offset、hash 和可复建配方。

已确定选出 12 个不同 source_id 的真实完整 Summary 回复：upstream train、quality good、context 400–16000 Unicode 字符、答案至少 120 词；按 CNN/DM 与 Recent News、upstream 是否有错误 span 组成四层，每层三条，固定 seed `20261020`、`sha256(seed:id)` 顺序且每 source 一条。不依据 verifier 预测挑选。六条有原 span、六条无原 span，但 span 并不等于完整 claim gold；选中的 7 条低于主集 800 estimated tokens 下限，保持自然全文并透明记录，没有填充或伪改长度。

固定 IDs、source_id、原 model/split/quality/temperature、非文本原 span 元数据和逐条 hash 在 `auxiliary/ragtruth-selection.json`。原始文件 SHA256：response 为 `e4c2e4ac24fff676d8984cc61c35d791612fadc58015335d97dd632375e18073`，source_info 为 `0dffc26ea9f3c1c3d7c7e8336b56ef1646e3cec876edffcca3c9c624d12d578b`。

重建分两层，不能把第一层误称完整打分数据：

1. `auxiliary/rebuild_ragtruth.py` 下载/核验固定上游两文件并选取原始记录，完整原 response 与 context 不变；该采集层没有 claim gold 或 Question 前缀，记录 `claim_annotation_status=not_performed`。本地 raw-selection artifact SHA256 为 `8344e25226138e8ff2e5f0238154ab8f3c3779281caefd1ad247472c11c8399f`。
2. `auxiliary/rebuild_ragtruth_scoring.py` 配合自编 annotation recipe，从固定原文的 Unicode intervals 本地还原 gold quote/anchor，并构造实际测量输入 `Question: {原 prompt 第一行 Summary 指令}\n\nAnswer: {完整原 response}`。原 response 字符串和原 span 坐标完整保留；gold anchor 才加 prefix 长度。公开 recipe 不存直接 quote/anchor 字段或完整原文/response，自编事实措辞可能与短原串重合。输出 blind、sealed gold、private cases 三份均核 hash；另生成只在私有目录使用的严格 manifest、逐条 decoded source_info 原文文件和仓库 MIT notice。manifest 的 license 字段明确 underlying third-party rights 未核定、仅私有采集，不能把新闻标成 MIT。

原 `ragtruth-claim-recipe.author-draft-1.json` 的 12 条、161 个作者 claim 及其 pending 元数据保留为历史交接快照。独立 AI reviewer 先完成并锁定 197 个盲判断，才打开作者 gold；集中裁决后另存 `ragtruth-claim-recipe.reviewed-1.json`，保留全部原回答/context，形成 12 条、170 个完整诊断标注。67 项变更或新增逐项获接受，103 项全字段精确不变，189 个引文和 170 个答案锚点逐字核对通过；13 组请求和 46 项主体/范围绑定均已解决。没有声称 human signoff。

主辅助评分只使用 `scoring-cases.jsonl` 的 9 条、125 个事实（111 S、12 U、2 C）。固定原 12 IDs 不变；2660、4100、5639 因真实文本的共享年份、因果附着或行为主体/修饰语附着存在多种合理读法，整例保留为非评分诊断，不把含糊 claim 偷删后继续给原完整答案算分。9 IDs、3 个排除 IDs、原因类别和裁决历史在公开 membership/status 文件中固定，选择发生在辅助 verifier 结果之前，未读取模型预测；该目的性小样本不能代表全部 RAGTruth。

审后配方实际重建的 12 条诊断三件套及 9 条评分三件套，都与接受包的原行字节投影相同。完整 12/170 和正式 9/125 均由现有严格消费者连同相邻 manifest 加载通过。新闻 decoded-field 原文和完整回复仍只在私有重建目录；公开配方只含自编标注、offset/hash 和固定 ID，短事实措辞可能与原文重合，但没有直接 quote/anchor 字段或完整新闻/回复。独立来源 reviewer 曾对 raw hash、interval hash、output hash 和 repository-license hash 四种失配验证安全拒绝；新增 membership 和子集输出 hash 也在写出前核验。脚本不执行推理，未报告辅助模型分数。公开 `ragtruth-review-status.reviewed-1.json` 明确区分原始私有审查 hash 与新序列化元数据投影，原 197 盲判断和锁未修改。

FActScore 的原子事实分解与 RAGTruth 的真实 response/错误 span 是方法参照和辅助来源；HaluEval 本轮没有装入主集。无需为点名来源而假称使用没有实际借入的数据或改造自然回复。

## 验证和交接证据

- 主候选严格加载：72 cases / 48 families / 668 claims，exit 0；manifest、许可/raw hashes、273 个 Unicode passage 映射、answer anchors 与引用逐字检查通过。
- `.multi-subflow/eval-v2/realistic-data/final-main-aggregate.json`：父端可读的最终统计、分离限制、组件/审查 hash；不含单个 test gold。
- `datasets/v2/realistic-draft/review-evidence/publication-manifest.json`：新增 60 条真实公开独审证据及投影规则，不依赖读者访问私有工作区来核对接受声明。
- `.multi-subflow/eval-v2/realistic-data/protected-after-authoring.json`：8 个既有受保护文件的前后 hashes 全部相等，含原 pilot、v1 和当时默认 main。
- `.multi-subflow/eval-v2/provenance-final-review/review.md` 与 `review-result.json`：独立来源、NOTICE、整合与辅助重建边界接受证据。
- 独立标签审查的原锁、逐项对照、裁决与受影响复核存各 reviewer 隔离子树；完整 test 只按已授权路径交独立 reviewer，父端只收聚合与 hashes。

本任务没有读取凭据、调用外部模型 API、启动 benchmark 或写 root main；真实调用、成本/时延、候选 verifier 质量和最终主集提升由唯一 live owner 另行记录。
