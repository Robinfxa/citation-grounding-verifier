# Annotation review queue

**Status: pending human annotation review.** This project record lists unresolved annotation and evidence questions. AI reviews and deterministic checks do not establish human verification. Personal exercises and interview preparation are stored separately from this repository.

Use the [revised pilot](../../datasets/v2/pilot.jsonl), [original draft](../../datasets/v2/pilot-author-draft-1.jsonl), [source mappings](../../datasets/v2/pilot.manifest.json) and [full disagreement records](annotation-review/comparison.json). Claim IDs below refer to the original draft; the revision metadata maps split claims to their new IDs.

| Check | Original claim(s) | Source-based question to resolve |
| --- | --- | --- |
| Missing evidence versus contradiction | p04-c09; p06-c09/c10 | Explain why an unqualified default-settings claim needs the flags exception, and why hash verification or a 15-minute cache cannot be inferred from a documented field/API. Identify what would constitute direct counterevidence. |
| Answer scope | p04-c10 | Find “later arithmetic” in the original answer and explain why an exact substring anchor still omitted a material assertion. Check the revised conversion-only wording. |
| Necessary versus sufficient condition | p07-c04 | Read the old and revised Rust quotations. Explain why “A implies B” alone does not justify “B requires A.” |
| Genuine multi-passage link | p01-c03 | Trace the named tar filter through every inherited restriction. Remove one necessary identity link mentally and explain what is lost. |
| Mode mapping and scope | p10-c05/c06 | Trace Read Uncommitted → Read Committed → the SELECT rule, including the heading that assigns the rule to the correct mode. |
| Numeric and version scope | p04-c04–c07; p03-c05 | Separate precision nine from rounding mode, and preserve the Python 3.13 / non-strict qualifier when judging the symlink-loop claim. |
| Atomicity | p06-c07; p12-c08 | Check the separate size/hash and function/procedure assertions, including the before/after ID mapping and shared answer anchors. |
| Evidence economy and difficulty | p02-c04; p05-c08 | Find sufficient single-passage evidence. Explain why these no longer count as necessarily cross-passage, and why a valid shorter quote should not be penalized for missing irrelevant prose. |

The [original AI review queue](annotation-review/human-review-queue.json) retains all issues and priorities. A later human record should include reviewer identity, time, case/claim IDs, decision, source-based reason and unresolved questions. Do not change its human status merely because an AI revision passed.

The main dataset has since expanded to 72 cases / 668 claims. Its [additional 60-case independent AI review](../../datasets/v2/realistic-draft/review-evidence/README.md) preserves original blind judgments, locked comparisons and affected acceptance. The cases above identify annotation boundaries; they are not evidence that a human reviewed the new test population.

## 最终结果高风险人工入口（仍未审）

以下全部保持未勾选。程序重放、父端有限代理抽查和原代理澄清均不等于 Robin 已完成逐项人工审阅。开发集标注问题继续保留。

- [ ] 核对[实际例子 E01/E02 及直接证据定位](final-20261020/failure-examples.md)：有效改述为何被 strict 漏计，Counter 的 gold 合写与预测三条拆写为何按冻结规则判 split；说明 split/extra 不自动等于事实错误，审计 F1 也不是通用 faithfulness 排名。
- [ ] 逐读[两条已确认审阅纠错](final-20261020/semantic-audit-adjudication.json)：A/r34-c07 与 B/r20-c10 为什么已有足够证据；核原票仍在，并核[独立敏感性](final-20261020/semantic-audit-correction-sensitivity.json)只把 Optimized evidence 100→102、保持分母 546。不得据两次定点发现估计全部 371 对的审阅误差率。
- [ ] 检查 B 的[锁定对齐与证据判断](final-20261020/semantic-audit/batch-02/evidence-review.json)：item-0017/r04-c09/prediction1 的条件范围为何仍 uncertain；对照原文本阶段记录，区分对齐疑点与标签争议，不事后改本轮 gold、alias 或原审阅票。
- [ ] 检查 E03 的 Flag 类身份前提，以及 E04/r32-c03 的 gold evidence 模板疑点：引文等于 gold 组且直接 span 代理为 true，为何仍可能缺 configured-filter-list 指代前提；同时确认其 E2E 文本未匹配、原 joint 分数没有通过。先保留未决，不把代理判断或 gold 模板任一方自动当作最终真值。
- [ ] 对照 E05–E08：解释 teardown 的“尝试/保证完成”、post-init 的 when-defined 条件和 Rust 完整允许列表的推理边界；将同家族复现与独立错误分开。协议 ERROR 不作 U，缺失 usage 不作零，也不猜测未记录的协议原因。
- [ ] 结合[固定 24 项审计](final-20261020/semantic-audit-analysis.json)与[天然回答辅助结果](ragtruth-20261020/README.md)，区分真实文档上的合成/受控回答、9 条天然 RAGTruth 回答及预测前整例排除。解释阶段 2 reasoning 可泄露方法风格、每项并非双审、私有天然全文不能由公开聚合替代；人工结论另记身份、时间、来源和未决项。

最终辅助测量已完成54/54项，实际46次调用（含1次输出修复），原执行者公开聚合重放退出0且18个私有原始文件字节一致。此执行完成不改变任何待人工审阅状态；原文、完整gold、预测和引文仍私有，公开聚合不能替代逐项人工核查。
