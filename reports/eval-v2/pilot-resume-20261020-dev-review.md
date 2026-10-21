# 开发集 pilot：有界非作者误差归因

复核续跑中全部三条成功端到端输出：p01/optimized、p02/minimal、p06/minimal。gold 与输出均可见，**不是盲态 test audit，不产生语义总体分数**。prediction index 与 passage index 均从 0 起。完整原句、最小证据和逐条覆盖在 [逐项证据](pilot-resume-20261020-dev-review.json)。

最重要的发现是：strict 文本失配、原子粒度和引用充分性是三个不同问题。完整上下文下，未发现需要把现有判定改为另一标签的反例；这不能替代逐条原子性或引文验收。p01 的直接反驳、p06 的“未说明验证/缓存”分别得到 CONTRADICTED 与 UNSUPPORTED，未把缺证据当反驳。

| 位置 | 归因及最小证据 | 行动与不确定性 |
| --- | --- | --- |
| p01-c03 ↔ pred2（F01） | `Choosing data also rejects` → `Choosing data rejects`。data 继承 tar_filter、后者拒绝 symlink 解析后越界路径的两段链接均在引文中。 | 明确的表面失配；不改 alias、gold 或 prompt 来追文本。 |
| p02-c01/c02/c03/c07 ↔ pred0/1/2/6（F02） | 省略 gold 中的 `sqlite3`，部分语序改写；False、legacy、None、immediately 等行为限定仍在 claim_text。原答案的 `For sqlite3 transaction control` 给出篇章实体。 | 本案内可对齐，但实体只隐含于上下文；不得自动当成独立自足 claim 的完全等价或补分。 |
| p02-c09 ↔ pred8（F03） | `context manager block` → `context manager's block`，`does not close` 保留。 | 表面失配；引文主体链接另见 F06。 |
| p02-c01 ↔ pred0（F04） | 已引 `set autocommit to False` 和 `sqlite3 ensures ... always open`；gold 还要求中间 PEP249/`This means` 文字。 | 较可能为代理保守；连接句删短仍有证据边界不确定性，不作最强实例。 |
| p02-c02/c03/c07 ↔ pred1/2/6（F05） | pred1 的立即替换事务句、pred2 的 `BEGIN DEFERRED` 句缺 False 分支；pred6 的 None 分支缺 LEGACY 外层条件。 | **实际引用条件缺口**。条件仍在抽取 claim，完整 source 支持标签；应补短模式条件，不能改判 UNSUPPORTED。 |
| p02-c09 ↔ pred8（F06） | 引文 `The context manager ... nor closes the connection` 未带 `A Connection object can be used as a context manager`。 | 引文主体链接缺口，中等置信；若允许完整 passage 主题补先行词，则可能属于代理保守。 |
| p06-c07a/c07b ↔ pred6（F07、F08） | `has size and hash ...` 两个属性均保留，但合并成一条；引文从 `Each file object returned` 开始，缺 `files() ... returns ...` 链接。 | **原子性合并 + 实际 API 引文链接缺口**。不能把一条静默补成两条满分，也不能说两个事实都漏抽。 |
| p06-c01 ↔ pred0（F09） | 引文只说 `returns an EntryPoints object`，未带紧邻的 `a collection of all EntryPoint objects`。 | collection 属性未由引用直接展示，中等置信；若类型名语义即被接受，则可视为代理保守。补短释义即可。 |
| p06-c03 ↔ pred2（F10） | 引文完整写 `entry_points passes keyword arguments through to select`；缺 gold 的 `Equivalently, since` 与 `::`。 | **明确的证据代理漏扣**，无需为衔接语扩大引用。 |
| p06-c05 ↔ pred4（F11） | `the values are returned unparsed ...` 缺 `metadata()` → 返回结构 → values 的接口链接。 | **实际引用主体缺口**；reasoning 中自行提到接口不能替代引文。 |
| p06-c06 ↔ pred5（F12） | PackageMetadata、json、metadata、JSON-compatible 都在引文中；仅缺 `per PEP566::`。 | **明确的证据代理漏扣**；断言未要求某 PEP 的合规性。 |

其余逐条关系均已核对；p01-c01/c06/c07 的直接反驳证据和 p06-c09/c10 的无证据判定理由保存在 JSON 的 `label_reasoning_controls`。未发现需改 gold verdict 的实质歧义。size/hash 的 gold 拆分符合原子性；实体继承和短引文类型语义属于已保留的边界不确定性。

当前 `MINIMAL` 已要求原子断言、保留限定和精确引用；`EXTRACT` 已更明确要求并列原子化；`JUDGE` 已明确要求引文带先行词与控制条件。因此若后续另有开发推理授权，最小候选是**仅向 MINIMAL 增加一句“引用集合须带主体/API 与所有上位条件，必要时补附近先行词”**，保持其他变量不变。原子拆分例子的增强须另做实验，不能与引文改动捆绑。本次未改 prompt、未调用 provider，未声称候选有效。

已机械核验 packet 中全部 answer anchor、gold quote、returned citation 的逐字子串合法性，并验证报告覆盖全部 gold 与 prediction；精确存在不代表语义充分。源码、datasets、reports、OpenSpec 和 Git 均未修改；只写本目录两个复核文件。无运行路径改动，日志实施审查不适用。

未验：oracle 两条输出、heuristic、超时/上游/预算失败、其余样本、总体方法比较、成本时延、运行冻结配置与当前提示文件的精确绑定，以及任何新提示效果。无需额外材料即可完成本次三条定性归因；若扩大到运行审计，才需另给对应冻结配置与原始记录。
