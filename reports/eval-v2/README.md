# Evaluation v2 — real-document benchmark

The original short fictional benchmark is retained as history. **The main dataset has been replaced with 72 reviewed real-document cases / 668 claims**, split into 24 dev and 48 held-out cases. The development comparison, controlled citation-prompt experiment, full held-out run, fixed stability subset, preselected semantic audit and separate natural-response measurement are complete. Both final populations were independently replayed against the fixed source checkpoint.

## What changed

Sources are pinned documentation from CPython, Rust, PostgreSQL, pytest and curl. Contexts contain 3,905–15,959 characters and answers contain 8–14 annotated claims. Question context, source mappings, controlled changes and answer anchors are explicit. The [data card](data-card.md) describes the actual population, label imbalance, limited cross-passage coverage and source dependence. Independent AI annotations were locked before author-label exposure; [public review evidence](../../datasets/v2/realistic-draft/review-evidence/README.md) preserves the disagreements and accepted revisions. Human review remains pending.

These answers are AI-authored on real sources. A separate fixed RAGTruth natural-response sample has completed annotation/reconstruction review: nine responses / 125 claims are eligible for scoring, while three responses remain whole-case ambiguity diagnostics. Its completed measurement is reported separately below. Longer inputs alone are not evidence of better benchmark quality or harder semantic judgments.

## Full held-out first observation

The [original full run](final-20261020/full-test/summary.json) completed all **288 jobs: 48 cases × three methods × two tracks**, with 240 provider calls, no retries or repairs, and no operation failures. Its 410 gold claims are 356 S / 37 C / 17 U. These are the first observations; the 16-case stability subset is reported separately below.

| Measure | Heuristic | Minimal | Optimized |
| --- | ---: | ---: | ---: |
| Oracle label accuracy | 19/410 | 406/410 | 407/410 |
| Oracle label macro F1 | 0.0304 | 0.9537 | 0.9642 |
| Oracle joint gold-evidence F1 | 0.0415 | 0.1707 | 0.2610 |
| End-to-end strict joint label F1 | 0.0000 | 0.0345 | 0.0333 |
| End-to-end strict joint gold-evidence F1 | 0.0000 | 0.0065 | 0.0093 |
| End-to-end exact cases | 0/48 | 0/48 | 0/48 |

**The strict end-to-end floor is largely a measurement limitation, not evidence of 97% factual failure.** Only 16 Minimal and 18 Optimized assertions matched the frozen text inventory; they produced 517 and 671 assertions respectively. Correct unregistered paraphrases and granularity differences are penalized. The preselected semantic audit below examines those effects without changing the main scores. Oracle label accuracy remains near its ceiling, so longer documents have not established broadly hard classification on this population.

Oracle false-support counts are 4/54 for Minimal and 2/54 for Optimized, with all 54 non-supported gold claims judged. In contrast, strict end-to-end non-supported judgment coverage is only 0/54 and 2/54; zero observed false support there is not a safety result. Claims missing strict matches remain in the denominator.

All those oracle false supports are among the **17 U claims**: U recall is 13/17 for Minimal and 15/17 for Optimized. The errors repeat across related dataclass/fixture cases, so they are not four or two independent failure types. Optimized also labels one of 37 C claims as U. This class-specific view exposes scope/condition boundaries hidden by the S-heavy overall accuracy; the source-based examples retain annotation caveats.

The family-paired 95% interval for Optimized minus Minimal oracle label accuracy is **−0.0073 to +0.0146**. Its oracle gold-evidence F1 advantage is **+0.0902 [0.0573, 0.1268]**, a benefit under that proxy. Both end-to-end strict joint-score difference intervals cross zero. These intervals resample 24 topic families, exclude annotation bias and unseen model variation, and do not establish independence across upstream projects. Full confusion matrices, per-class scores, category/origin slices and interval definitions remain in the saved summary.

| First-run end-to-end resources, 48 cases each | Minimal | Optimized |
| --- | ---: | ---: |
| Provider calls | 48 | 96 |
| Input / output tokens | 135,252 / 61,292 | 182,913 / 90,387 |
| Median / p95 operation seconds | 26.56 / 35.94 | 43.48 / 56.05 |

The heuristic makes no provider calls. Across both tracks and all methods, the first run used 607,805 input and 230,046 output tokens; subscription dollar cost is unknown. Benchmark deadlines were 120 seconds per provider call and 240 seconds per operation. This does not demonstrate the same live success rate under the service's default 60-second operation deadline. Minimal remains the default; a conditional oracle citation-proxy benefit does not establish an overall advantage for the extra end-to-end call.

## Completed first-run semantic audit

Two non-author AI reviewers examined disjoint 12-case batches, covering the same three methods on **24 preselected cases / 203 gold claims / 24 topic families**. They locked text alignment before seeing labels and citations, then judged 371 equivalent pairs across the methods. [Original records and aggregation](final-20261020/semantic-audit-analysis.json) retain splits, merges, extra assertions, scope changes and uncertainty without automatic credit.

| End-to-end measure on this audit subset | Minimal | Optimized |
| --- | ---: | ---: |
| Gold / predicted assertions | 203 / 262 | 203 / 343 |
| One-to-one semantic equivalents | 139 | 119 |
| Semantic joint label F1 | 276/465 = 0.5935 | 236/546 = 0.4322 |
| Original semantic joint evidence F1 | 264/465 = 0.5677 | 200/546 = 0.3663 |

Among those equivalents, Minimal had 138 correct labels and one incorrect label; Optimized had 118 correct and one uncertain label. These conditional counts do not measure the judgments on unmatched claims. The main observed loss is extraction/granularity under the frozen atomicity policy, plus evidence sufficiency, rather than broadly difficult factual classification. The audit does not rescore all 48 test cases or make 24 topic families independent upstream projects.

Granularity disagreements also expose limitations of the gold inventory. For example, one gold claim combines hashable Counter keys with zero and negative counts; Optimized expresses these as three assertions. The frozen one-to-one policy withholds full credit, but that alone does not establish a factual error. Likewise, an `extra` assertion means unmatched to gold, not necessarily false. The audit F1 gap is therefore not a general faithfulness ranking.

Parent spot-checking found two overly strict evidence judgments, each acknowledged by its original reviewer. Both concern Optimized: one quote already explains that rewriting skips unavailable caching; another general lifetime-permission rule supports the claim's narrower condition. [Original judgments and acknowledgements](final-20261020/semantic-audit-adjudication.json) remain separate. Applying only these two changes gives a [supplemental evidence F1](final-20261020/semantic-audit-correction-sensitivity.json) of **204/546 = 0.3736** for Optimized, with all denominators unchanged. This targeted correction is not exhaustive validation or an estimated reviewer error rate.

One locked alignment remains uncertain after scope was revealed; a warning-filter evidence template also has a potential missing-antecedent issue. No gold, aliases or main scores were repaired after testing. Some prediction reasoning identifies a lexical baseline, so [full method blinding was not achieved](final-20261020/semantic-audit/exposure-disclosure.json). Each item had one primary AI reviewer; this was not an inter-rater agreement study, and human review remains pending.

## Stability and retained operational failure

The [fixed 16-case subset](final-20261020/repeated-analysis.json) has three observations per method/track: its rows from the full run plus two additional runs. It contains **16 source families**, not 48 independent samples. Each method/track has 408 gold-claim observations from 136 distinct gold claims.

| Pooled measure across these three observations | Minimal | Optimized |
| --- | ---: | ---: |
| Oracle label accuracy | 402/408 = 0.9853 | 403/408 = 0.9877 |
| Oracle gold-evidence F1 | 0.1691 | 0.2941 |
| End-to-end strict joint label F1 | 0.0353 | 0.0274 |
| End-to-end strict joint gold-evidence F1 | 0.0155 | 0.0109 |
| End-to-end operation success | 47/48 | 48/48 |

Oracle evidence F1 varied from 0.1618–0.1765 for Minimal and 0.2794–0.3088 for Optimized. The pooled Optimized-minus-Minimal evidence advantage is +0.1250 [0.0827, 0.1714]; its oracle label difference is +0.0025 [−0.0145, 0.0219]. Both end-to-end joint-score difference intervals cross zero. These family-paired intervals preserve all three observations together and describe family-sample sensitivity; three runs do not characterize all future model variability.

Across the three original main blocks, **479/480 jobs succeeded and one failed**, using **400/600 allowed provider attempts**, with no retries or repairs. Repeat 2 exited with code 2 because Minimal end-to-end `v2-test-r08` returned `provider_protocol_error`. Its original row and all gold denominators remain; it was not replaced. The known resource subtotal is 981,844 input / 388,310 output / 3,328 cached input tokens. That failure has unknown usage, so the total and subscription dollar cost remain unknown. [Execution receipt](final-20261020/execution-receipt.json) and [safe error diagnosis](final-20261020/error-diagnosis.json) preserve this distinction.

The [eight source-linked examples](final-20261020/failure-examples.md) cover valid paraphrases rejected by strict matching, claim granularity, missing identity/conditions, possible gold-template defects, actual label errors and the protocol failure. They explain what each observation does—and does not—establish.

## Separate natural-response RAGTruth result

The [RAGTruth auxiliary](ragtruth-20261020/README.md) measures **nine original model responses / 125 reviewed claims / nine source families**. Three of the original 12 selected responses were excluded from scoring for unresolved annotation ambiguity before predictions. This is a purposive sample, not a reproduction of the complete RAGTruth benchmark or an estimate of production error prevalence. HaluEval and FActScore informed the [method/source research](../../docs/research/eval-v2-sources.md); their records were not imported into main.

All **54 jobs succeeded**, using **46/90 provider attempts**, including one output repair and no transport retries. Known and complete usage is 66,143 input / 62,978 output tokens. Subscription dollar cost remains unknown. These observations use the same frozen runtime/model and are not pooled with the documentation population.

| Auxiliary measure | Heuristic | Minimal | Optimized |
| --- | ---: | ---: | ---: |
| Oracle label accuracy | 12/125 | 123/125 | 122/125 |
| Oracle label macro F1 | 0.0584 | 0.8617 | 0.8488 |
| Oracle joint gold-evidence F1 | 0.0960 | 0.4400 | 0.6960 |
| End-to-end strict joint label F1 | 0.0000 | 0.0597 | 0.0130 |
| End-to-end strict joint gold-evidence F1 | 0.0000 | 0.0373 | 0.0000 |

There are 111 S / two C / 12 U gold claims. Both LLM methods identify all 12 U claims, but only one of the two C claims; the tiny C denominator makes macro F1 sensitive to a single judgment. Neither has oracle false support on these 14 non-S claims. Strict end-to-end non-S coverage is only 1/14 for Minimal and 0/14 for Optimized, so its zero observed false-support counts are uninformative. Oracle accuracy remains high on this small natural sample too.

Optimized's oracle evidence-proxy advantage is +0.2560 [0.2034, 0.3047]. Strict end-to-end label/evidence differences favor Minimal under the frozen matching proxy, but only eight and two predictions match gold. **There was no semantic output audit on this auxiliary sample**, so those differences do not establish semantic superiority. The nine-family resampling, single observation, purposive selection, pre-result exclusions and AI annotations limit generalization.

End-to-end median/p95 seconds are 38.75/47.08 for Minimal and 62.23/90.91 for Optimized; calls are 9 versus 19, including the repair. These measured tradeoffs reinforce retaining Minimal as the default without claiming established accuracy superiority. Complete aggregate denominators, uncertainty and resources are in [aggregate-results.json](ragtruth-20261020/aggregate-results.json).

Original news text and predictions remain private. Public IDs, hashes, annotations and recipes support input reconstruction; they cannot reconstruct stochastic model outputs. The [offline aggregate replay](ragtruth-20261020/replay-aggregate.py) therefore requires the holder's original private run. The main documentation runs and their replay are fully public.

## Completed development measurements

The [development comparison](completion-dev-20261020/README.md) covers the original 12 dev cases / 126 claims, all three methods and both tracks. Its 72 analytical records contain 71 successes and one original protocol error. Later runs fill only previously unattempted jobs; they do not replace a failure with a better result. This is a mapped cross-run analysis, not a successful single CLI run. It used 62/320 new attempts, including two availability checks. Unknown usage and subscription dollar costs remain unknown.

| End-to-end strict proxy | Heuristic | Minimal, original prompt | Optimized |
| --- | ---: | ---: | ---: |
| Joint label F1 | 0.0614 | 0.7173 | 0.6926 |
| Joint label + gold-evidence F1 | 0.0614 | 0.2954 | 0.6148 |
| Exact cases | 0/12 | 0/12 | 1/12 |

Both LLMs scored 1.0 oracle label macro F1 on these development claims. Thus lower end-to-end scores do not by themselves establish difficult judgment: extraction, exact surface matching and citation coverage contribute. [Development attribution](completion-dev-20261020/development-findings.json) separates those effects and actual condition/identity citation gaps.

The [C01 ablation](ablation-20261020/README.md) changed only one Minimal end-to-end citation instruction, with two observations per condition. Gold, aliases, scorer, model and transport stayed fixed. New blocks used 36/216 attempts; the original control error remains in the primary denominator. Pooled strict evidence F1 increased from **0.2845 to 0.6384**; joint-label F1 increased from **0.7258 to 0.7717**, but its family-paired interval crossed zero. Inspection confirmed improvements to known governing-condition citations, while a localcontext merge and missing antecedent remained. These are development observations, not final-test or general semantic-accuracy claims.

In the complete second observation, output tokens rose 22.6%, total operation time 23.1%, and quotation characters 79.4%. The exact instruction was adopted with those tradeoffs. The default remains Minimal; no test results have informed tuning.

## Frozen final design

The completed comparison is 48 held-out cases × three methods × two tracks. A preselected 16-case subset received two additional repetitions; its first observation is the full run. A stratified 24-case audit subset contains one case per held-out topic family. Selection uses metadata and a fixed seed before model outputs, not observed successes or failures. [Selection artifacts](final-20261020/selection.json) bind the promoted main dataset.

The final allowance is 600 provider attempts across three blocks (360/120/120), including repairs, with zero transport retries. Individual operation errors remain in the records and denominators; quota/budget stops leave explicit NOT_RUN records. Further blocks pause after quota/budget stops or a block model-error rate of at least 10%. The same Codex / `gpt-6.1-sol` configuration uses 120-second provider and 240-second operation deadlines. Requested output limit 8,192 is **not applied** by the Codex route; effective limit is unknown. The [pre-inference freeze](final-20261020/experiment-plan.json) binds source commit `324559dccba4624dfa803849f5fd26284c7b27f4`, input/settings hashes and [exact commands](final-20261020/commands.md).

The [audit policy](audit-policy.md) locks anonymous claim alignment before labels and evidence are revealed. Only equivalent one-to-one assertions receive full alignment credit; merges, splits and scope changes remain distinct. Literal quote validity, exact gold-span coverage and semantic sufficiency are separate measures. Family-paired intervals retain dependent repeated observations; cases from the same upstream projects may remain correlated.

[Independent parent acceptance](final-20261020/parent-acceptance.json) reproduced all 294 main-run files, eight stability groups, two audit batches and the correction sensitivity. The separate auxiliary replay reproduced all 18 private files and their public aggregate. Both actual processes exited 0 without inference, network or credential access. Replays verify saved numerical results and review bindings; they do not create fresh semantic judgments. Original failures and unknown usage remain unchanged.

## Inspect and reproduce

For saved results, use the [main fixed-source replay recipe](final-20261020/README.md#portable-offline-replay). It requires no model access. The [auxiliary recipe](ragtruth-20261020/README.md#actual-offline-replay) additionally requires the original private saved run; public input reconstruction does not reproduce stochastic outputs.

- [Main data card](data-card.md), [experiment protocol](protocol.md), [main promotion receipt](final-20261020/main-promotion.json)
- [Development records and fixed-source replay](completion-dev-20261020/README.md), [single-factor experiment and replay](ablation-20261020/README.md)
- [Original pilot review](annotation-review/README.md), [new independent reviews](../../datasets/v2/realistic-draft/review-evidence/README.md), [human queue](human-review.md)
- [Historical v1 report](../2026-10-15/README.md), [fixed-source replay checks](baseline-checks.json)
- [Earlier partial pilot](pilot-resume-20261020.md), [staged recovery](pilot-recovery-20261020.md); their 63/150 historical counter is preserved separately
- [AI use/workflow](../../AI_used.md), [code walkthrough](../../docs/code-walkthrough.zh-CN.md), [interview exercises](../../docs/interview-self-check.zh-CN.md)

The [final fresh installation](final-offline-verification.json) passed 861 tests, lint and main validation with locked dependencies in a new environment. [Real long-development-input consumers](final-consumer-verification.json) passed HTTP success → safe rejection → recovery and byte-identical CLI report replay without inference. The earlier 510-test [offline receipt](verification.json) and [model-error-stop review](model-error-stop-verification.json) remain valid only for their stated code/inputs. Optional Jev smoke records remain supplementary and do not establish calibration or a cost/speed advantage.
