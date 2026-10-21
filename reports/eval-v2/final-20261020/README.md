# Final test evaluation — 2026-10-20

The main sequence is complete: 479 OK, one retained ERROR and zero NOT_RUN across 480 requested jobs, with 400 measured provider calls. The intact first run is the primary result. Oracle labels are near their ceiling, while strict end-to-end identity has a severe paraphrase/granularity floor. The bounded semantic audit exposes this measurement gap and retains actual extraction, scope and evidence limitations; it does not establish a universally better method or harder factual classification.

| Population | Cases | Gold claims per method/track | Source families | Use |
|---|---:|---:|---:|---|
| Original test | 48 | 410 | 24 | Primary, both tracks |
| Stability subset | 16 × 3 observations | 136 per repetition | 16 | Repeated sensitivity only |
| Semantic audit | 24 | 203 | 24 | First-run end-to-end only |
| Natural RAGTruth auxiliary | 9 | 125 | 9 | [Separate population and artifacts](../ragtruth-20261020/) |

Runtime source is pinned to commit `324559dccba4624dfa803849f5fd26284c7b27f4`, fingerprint `cd15430a02b364c2f6ddef034e6ef046b335dd99b3678d3dada5186e31dd89a6`. Main annotation version is `v2-realistic-reviewed-1`. The [frozen plan](experiment-plan.json) binds source, dataset, settings, selections and policy. Gold remains agent-authored and independently AI-reviewed; human review is pending.

## Primary first-run results

The original full-test run contains 48 cases, 410 gold claims and 24 source families, with two cases per family. All 288 requested jobs succeeded; the 192 model operations made 240 provider calls. This primary result is an intact original run, not a recovery composition.

The sources are real, licensed technical documents; the answers are agent-generated or controlled mutations. They are distinct from the nine natural RAGTruth answers reported separately. The full main dataset has 598 SUPPORTED claims out of 668; test has 356 S / 37 C / 17 U. This imbalance limits difficulty claims.

Oracle supplies the frozen gold claims directly and preserves their identity and cardinality. Both model methods are close to the classification ceiling. End-to-end strict text/alias matching finds very few claims, so its low F1 cannot establish that factual classification became much harder. This evaluation chiefly adds long contexts, dense extraction and evidence-scope demands.

### Oracle: labels and conservative evidence proxy

Each method has 48 requests and 410 gold claims. Joint evidence requires a correct label and literal coverage of a frozen sufficient gold-quote set. It is a span proxy, not a semantic sufficiency judgment.

| Method | Correct labels | Macro F1 | S / C / U F1 | Non-S judgment coverage | False support | Evidence F1, span proxy | Exact cases |
|---|---:|---:|---|---:|---:|---:|---:|
| Heuristic | 19/410 | 0.030391 | 0.011173 / 0.000000 / 0.080000 | 54/54 | 0/54 | 0.041463 | 0/48 |
| Minimal | 406/410 | 0.953693 | 0.994413 / 1.000000 / 0.866667 | 54/54 | 4/54 | 0.170732 | 0/48 |
| Optimized | 407/410 | 0.964197 | 0.997199 / 0.986301 / 0.909091 | 54/54 | 2/54 | 0.260976 | 0/48 |

| Method | Gold class | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| Heuristic | SUPPORTED | 2/2 = 1.000000 | 2/356 = 0.005618 | 0.011173 |
| Heuristic | CONTRADICTED | 0/0 = null | 0/37 = 0.000000 | 0.000000 |
| Heuristic | UNSUPPORTED | 17/408 = 0.041667 | 17/17 = 1.000000 | 0.080000 |
| Minimal | SUPPORTED | 356/360 = 0.988889 | 356/356 = 1.000000 | 0.994413 |
| Minimal | CONTRADICTED | 37/37 = 1.000000 | 37/37 = 1.000000 | 1.000000 |
| Minimal | UNSUPPORTED | 13/13 = 1.000000 | 13/17 = 0.764706 | 0.866667 |
| Optimized | SUPPORTED | 356/358 = 0.994413 | 356/356 = 1.000000 | 0.997199 |
| Optimized | CONTRADICTED | 36/36 = 1.000000 | 36/37 = 0.972973 | 0.986301 |
| Optimized | UNSUPPORTED | 15/16 = 0.937500 | 15/17 = 0.882353 | 0.909091 |

The [original summary](full-test/summary.json) contains all three-class confusion matrices, per-class numerator/denominator values, and descriptive category/origin/tag slices. Overlapping tags are not independent populations. Heuristic has only 19/410 correct oracle labels, despite zero false support; its largely unsupported output must not be read as reliable verification.

### End-to-end: strict identity and coverage

All 410 gold claims remain in recall denominators; extra and duplicate predictions remain in precision denominators. Matching is verdict-blind, one-to-one and limited to frozen text/aliases after whitespace normalization.

| Method | Predictions | Strict matches | Omitted gold | Extra predictions | Decomposition F1 | Joint-label F1 | Joint-evidence F1 | Non-S coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Heuristic | 311 | 1 | 409 | 310 | 0.002774 | 0.000000 | 0.000000 | 0/54 |
| Minimal | 517 | 16 | 394 | 501 | 0.034520 | 0.034520 | 0.006472 | 0/54 |
| Optimized | 671 | 18 | 392 | 653 | 0.033302 | 0.033302 | 0.009251 | 2/54 |

Minimal/Optimized have zero strict false support out of 54 non-S gold claims, but judgment coverage is only 0/54 and 2/54. Those zeros are not evidence of a low false-support propensity. All 16/18 strictly matched model claims have correct labels; this does not establish the correctness of unmatched claims.

Literal citation validity is 487/487 and 461/461 for model oracle, and 576/576 and 701/701 for model end-to-end. Literal existence does not establish entity identity, antecedents, conditions or entailment. Model exact-case success is 0/48 in both tracks.

### Paired source-family sensitivity

Optimized minus Minimal; 24 source-family clusters, 10,000 paired percentile resamples, seed 20261015, 95% intervals. The two cases within a family stay together.

| Track | Metric | Difference | 95% interval | Defined / undefined draws |
|---|---|---:|---|---|
| oracle | joint_label_f1 | +0.002439 | [-0.007317, 0.014563] | 10000 / 0 |
| oracle | joint_evidence_f1 | +0.090244 | [0.057279, 0.126835] | 10000 / 0 |
| end-to-end | joint_label_f1 | -0.001217 | [-0.006429, 0.006701] | 10000 / 0 |
| end-to-end | joint_evidence_f1 | +0.002778 | [-0.002209, 0.011056] | 10000 / 0 |

Oracle has a positive span-proxy difference, not demonstrated semantic evidence superiority. Its label interval crosses zero. Strict end-to-end label and evidence intervals also cross zero at very low matching coverage. These intervals describe source-sample sensitivity, not annotation bias or all model randomness. Degenerate exact-case [0,0] intervals do not prove zero uncertainty.

## Fixed subset repeated across three runs

The 16 preselected cases each have one observation from full-test and one from each of repeat-02/repeat-03. This is 48 observations, 136 gold claims per repetition and 16 independent source families per method/track; repetitions add no new source families. All ERROR/NOT_RUN outcomes remain in the original denominators. The 48-case primary population is not replaced by this subset.

| Method / track | Label F1, repetitions 1 / 2 / 3 | Evidence F1, repetitions 1 / 2 / 3 | Pooled label / evidence F1 |
|---|---|---|---|
| heuristic/oracle | 0.036765 / 0.036765 / 0.036765 | 0.036765 / 0.036765 / 0.036765 | 0.036765 / 0.036765 |
| minimal/oracle | 0.985294 / 0.985294 / 0.985294 | 0.161765 / 0.176471 / 0.169118 | 0.985294 / 0.169118 |
| optimized/oracle | 0.992647 / 0.985294 / 0.985294 | 0.308824 / 0.279412 / 0.294118 | 0.987745 / 0.294118 |
| heuristic/end-to-end | 0.000000 / 0.000000 / 0.000000 | 0.000000 / 0.000000 / 0.000000 | 0.000000 / 0.000000 |
| minimal/end-to-end | 0.026316 / 0.040816 / 0.038961 | 0.006579 / 0.020408 / 0.019481 | 0.035320 / 0.015453 |
| optimized/end-to-end | 0.027397 / 0.027473 / 0.027248 | 0.010959 / 0.010989 / 0.010899 | 0.027372 / 0.010949 |

Minimal/end-to-end repetition 2 includes the retained r08 protocol ERROR. No failed result was replaced and no best repetition was selected. Strict scores still depend strongly on wording and extraction granularity, so a higher per-run value is not a failure-free quality guarantee.

Optimized minus Minimal, pooled within the same 16 source-family clusters; 10,000 resamples, seed 20261015, 95% intervals:

| Track | Metric | Difference | 95% interval | Defined / undefined draws |
|---|---|---:|---|---|
| oracle | joint_label_f1 | +0.002451 | [-0.014493, 0.021898] | 10000 / 0 |
| oracle | joint_evidence_f1 | +0.125000 | [0.082725, 0.171362] | 10000 / 0 |
| end-to-end | joint_label_f1 | -0.007948 | [-0.029220, 0.009465] | 10000 / 0 |
| end-to-end | joint_evidence_f1 | -0.004504 | [-0.027217, 0.015195] | 10000 / 0 |

Oracle again shows a positive span-proxy difference, with no established label advantage. Strict end-to-end differences cross zero. The paired macro-F1 intervals have 9963 defined and 37 undefined draws for each track; none were forced defined. Full per-repetition numerator/denominator values, paired deltas and limitations are in [repeated-analysis.json](repeated-analysis.json).

## Semantic audit of the fixed 24 cases

The preselected 24 first-run end-to-end cases cover 24 actual source families, 203 gold claims per method and 72 case-method items. Two fresh AI instances, configured as gpt-6.1-sol/max, reviewed disjoint 12-case batches. Each item had one reviewer, not two independent ratings.

Stage 1 exposed only answer/gold/prediction texts. Every gold and prediction was partitioned exactly once. Only one-to-one equivalent pairs receive semantic decomposition credit; merged, split, scope_changed, missing, extra, duplicate and uncertain relations do not receive automatic credit. Original stage-1 votes were hash-locked before the same reviewer saw context, labels, reasoning and citations for stage 2. The original gold, aliases, strict scores and all review bytes remain unchanged.

| Method | Gold / predictions | Equivalent | Label correct | Evidence correct | Strict label F1 on the same 24 cases | Semantic label F1 | Semantic evidence F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| Heuristic | 203 / 158 | 113 | 1 | 1 | 0.000000 | 0.005540 | 0.005540 |
| Minimal | 203 / 262 | 139 | 138 | 132 | 0.030108 | 0.593548 | 0.567742 |
| Optimized | 203 / 343 | 119 | 118 | 100 | 0.029304 | 0.432234 | 0.366300 |

Every semantic F1 retains all gold and predictions: its numerator is twice the credited count and its denominator is gold plus predictions. Semantic evidence additionally requires a correct label and sufficient literal-valid evidence, or a correctly labeled citation-free U. The [audit analysis](semantic-audit-analysis.json) preserves precision/recall/F1 denominators and all label/evidence/economy categories.

| Method | Merged | Split | Scope changed | Extra | Duplicate | Uncertain relations |
|---|---:|---:|---:|---:|---:|---:|
| Heuristic | 35 | 0 | 5 | 0 | 0 | 4 |
| Minimal | 1 | 50 | 7 | 4 | 1 | 4 |
| Optimized | 1 | 74 | 5 | 24 | 6 | 3 |

Relation values count groups, not gold claims. Minimal has 138/139 correctly labeled equivalents; Optimized has 118/119 correct and one uncertain. Much of the descriptive joint-score difference therefore concerns frozen granularity, additional output and evidence, rather than classification of aligned claims. Heuristic aligns 113 propositions but labels only one correctly.

Gold can bundle propositions that a reasonable extraction separates: Counter hashable keys, zero counts and negative counts are one frozen gold claim but three Optimized predictions in E02. Its split penalty is a contract-granularity effect, not evidence that those predictions are false. Extra means no equivalent frozen gold, not automatically a false assertion. Audit F1 is conditional on these choices and is not a universal faithfulness ranking or a rescore of all 48 cases.

### Review error, correction sensitivity and blinding

Two targeted checks found overly strict evidence votes, acknowledged by the same original reviewers: batch01/item-0000/r34-c07/prediction7 and batch02/item-0007/r20-c10/prediction5, both Optimized. The original insufficient votes and original aggregate remain intact. The [adjudication sidecar](semantic-audit-adjudication.json) records the challenge, original vote, reviewer acknowledgement and exact review/lock hashes.

The separately labeled [two-vote sensitivity](semantic-audit-correction-sensitivity.json) changes Optimized evidence credit from 100 to 102 with the same denominator 546: F1 0.366300 → 0.373626. Labels, alignment, Minimal and all other votes are unchanged. This is not exhaustive correction; targeted discoveries cannot estimate a reviewer error rate.

An unresolved template issue is also retained: r32-c03 returns a quote equal to its gold evidence group and the frozen evidence_covered function returns true, but the reviewer flags a missing configured-filter-list antecedent. Strict text identity did not match, so the original end-to-end pair received no joint credit. This remains a gold-span/semantic sufficiency question for future human review, not an applied correction or automatically a model failure.

Method names and keys were hidden, but full method blindness was not achieved: A reported original reasoning that calls itself a “conservative lexical baseline.” Stage 1 was already locked. Stage 2 also exposed frozen labels/rationales, so it is not a fresh independent blind annotation. AI instances are not independent humans or independent model families; no human review or inter-rater agreement is claimed. The coordinating agent separately replayed bindings, counts and the two corrections; it did not semantically re-review all 371 pairs. Resource tables cover the tested system’s provider calls and exclude AI reviewer compute.

## Measured examples and human review

[Eight illustrative examples](failure-examples.md) directly link case/gold/context, original prediction rows, pinned local sources and passage maps. Their [JSON](failure-examples.json) preserves original judgments and exact row/file hashes; the [locator verification](failure-examples-verification.json) is structural, not a new semantic vote. E01–E04 cover paraphrase, granularity, entity evidence and a gold-template question; E05–E07 are the seven oracle disagreements from only three source families; E08 is the retained repeat-02 protocol failure. Conditional/closed-list interpretation and annotation sensitivity remain explicit.

The [human review queue](../human-review.md) now includes final examples, both confirmed review corrections, scope uncertainty and template questions. All items remain unchecked. Existing pilot exercises remain available.

## Original full-run resources and operational limits

CLI wall time was 5281.629 seconds. Operation sums below include failed operations where present and differ from CLI wall time, which also includes reporting. The first full run has complete usage: 607805 input, 230046 output and 0 cached input tokens; all returned models are gpt-6.1-sol. Subscription tokens are not dollar cost.

| Method / track | Provider calls | Input / output tokens | Operation sum s | Median s | p95 s |
|---|---:|---|---:|---:|---:|
| heuristic/end-to-end | 0 | 0 / 0 | 2.082 | 0.029 | 0.112 |
| heuristic/oracle | 0 | 0 / 0 | 2.224 | 0.039 | 0.095 |
| minimal/end-to-end | 48 | 135252 / 61292 | 1323.607 | 26.556 | 35.939 |
| minimal/oracle | 48 | 136924 / 36121 | 817.158 | 16.181 | 20.871 |
| optimized/end-to-end | 96 | 182913 / 90387 | 2000.656 | 43.476 | 56.053 |
| optimized/oracle | 48 | 152716 / 42246 | 955.389 | 18.471 | 26.771 |

Settings were Codex/gpt-6.1-sol, 120 seconds per provider call and 240 seconds per operation, at most six attempts per operation and zero transport retries. Requested `max_output_tokens=8192` is not applied on this Codex path; effective cap is null. The service default operation timeout is 60s. Benchmark success with 240 seconds per operation does not establish success under that default; no extra counterfactual calls or rescoring were added.

The four new terminology calibration checks cover attempts/retries and submission/execution identity in both directions. They prove strict scorer boundary behavior and preserved FN/FP denominators, not model semantic proficiency. [Actual calibration receipt](terminology-calibration-verification.json): 4 passed, targeted lint passed, zero provider calls. The historical full-suite receipt is not relabeled as a new full-suite run.
## Execution, retained failure and whole-sequence resources

| Original block | Jobs | OK / ERROR / NOT_RUN | Provider calls | Usage complete | CLI wall seconds |
|---|---:|---|---:|---|---:|
| full-test | 288 | 288 / 0 / 0 | 240 | true | 5281.629 |
| repeat-02 | 96 | 95 / 1 / 0 | 80 | false | 1777.883 |
| repeat-03 | 96 | 96 / 0 / 0 | 80 | true | 1841.293 |

All 480 jobs have known terminal outcomes: 479 OK, one ERROR, zero NOT_RUN. The 320 model operations made 400 known provider calls out of the separate 600-attempt allowance; 200 were unused. Retries and repairs are zero. Native quota/budget, cleanup, source and input integrity boundaries did not fail.

Known usage subtotal is 981844 input, 388310 output and 3328 cached input tokens. Whole token usage is unknown because the original repeat-02 protocol error has incomplete usage and no returned model. Its zero token placeholders are not zero cost. Whole dollar cost remains unknown. Operation-time sum across all 480 jobs, including the error, is 8626.122 seconds; this is distinct from CLI wall time.

The [execution receipt](execution-receipt.json) binds each original run and its hashes. [Safe error diagnosis](error-diagnosis.json) retains the r08 Minimal/end-to-end provider_protocol_error, one charged call and no retry/repair. Existing safe events provide no protocol_reason; no HTTP/SSE branch, timeout, quota or prompt cause is inferred. No upstream body was captured and the failed operation was not rerun.

The [experiment plan](experiment-plan.json), [commands](commands.md), selections and audit-policy amendment are preserved pre-call records. Their historical preparation wording is not a current execution-status claim; terminal status is in execution-receipt.json. Runtime/data/gold/aliases/prompts/scorer were not changed in response to test results.
## Portable offline replay

The public consumer was actually executed from a fresh archive of the pinned source commit. It exited 0 in 387.392 seconds, regenerated identical reports for all 294 original run files, rebuilt eight repeated-analysis groups, both audit batches and the two-vote correction sensitivity. Network, inference, settings and credential loading were guarded; no new provider calls were made. See the [actual replay receipt](offline-replay-verification.json).

From a checkout with the project dependencies installed:

```sh
final_replay_source=$(mktemp -d)
git archive 324559dccba4624dfa803849f5fd26284c7b27f4 src | tar -x -C "$final_replay_source"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$final_replay_source/src" .venv/bin/python reports/eval-v2/final-20261020/replay-results.py
```

The consumer enforces the exact source fingerprint and original run hashes. It recomputes numerical summaries and verifies recorded review bindings; it does not perform fresh semantic judgments. The licensed main run inputs, outputs, manifests and source snapshots are public, allowing this replay without model access. Natural-response replay has a separate private-artifact boundary.

The original `source_archive_sha256` identifies an uncompressed tar of `src` plus 96 explicitly selected checkpoint paths, not the whole repository. It was rebuilt byte-for-byte, including all 28 runtime hashes and checkpoint input hashes; [exact arguments and verification](source-archive-reconstruction.json) are public. The frozen commands.md example exports a broader datasets subtree, and the replay recipe above exports only src. Their tar bytes differ by packaging scope while the required content hashes remain enforced. No frozen plan, command or original run was changed.
