# Evaluation v2 — real-document benchmark

The original short fictional benchmark is retained as history. **The main dataset has been replaced with 72 reviewed real-document cases / 668 claims**, split into 24 dev and 48 held-out cases. The development comparison and a controlled citation-prompt experiment are complete. Final test measurement is running against the fixed source checkpoint; stability repeats and the blinded semantic audit follow the prespecified design.

## What changed

Sources are pinned documentation from CPython, Rust, PostgreSQL, pytest and curl. Contexts contain 3,905–15,959 characters and answers assert 8–14 facts. Question context, source mappings, controlled changes and answer anchors are explicit. The [data card](data-card.md) describes the actual population, label imbalance, limited cross-passage coverage and source dependence. Independent AI annotations were locked before author-label exposure; [public review evidence](../../datasets/v2/realistic-draft/review-evidence/README.md) preserves the disagreements and accepted revisions. Human review remains pending.

These answers are AI-authored on real sources. A separate fixed RAGTruth natural-response sample has completed annotation/reconstruction review: nine responses / 125 claims are eligible for scoring, while three responses remain whole-case ambiguity diagnostics. Its measurement has not started and will not be pooled with main. Longer inputs alone are not evidence of better benchmark quality or harder semantic judgments.

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

## Frozen final design and remaining work

The planned comparison is 48 held-out cases × three methods × two tracks. A preselected 16-case subset receives two additional repetitions; its first observation is the full run. A stratified 24-case audit subset contains one case per held-out topic family. Selection uses metadata and a fixed seed before model outputs, not observed successes or failures. [Selection artifacts](final-20261020/selection.json) bind the promoted main dataset.

The final allowance is 600 provider attempts across three blocks (360/120/120), including repairs, with zero transport retries. Individual operation errors remain in the records and denominators; quota/budget stops leave explicit NOT_RUN records. Further blocks pause after quota/budget stops or a block model-error rate of at least 10%. The same Codex / `gpt-6.1-sol` configuration uses 120-second provider and 240-second operation deadlines. Requested output limit 8,192 is **not applied** by the Codex route; effective limit is unknown. The final source commit, input/settings hashes and exact commands must be frozen before calls.

The [audit policy](audit-policy.md) locks anonymous claim alignment before labels and evidence are revealed. Only equivalent one-to-one assertions receive full alignment credit; merges, splits and scope changes remain distinct. Literal quote validity, exact gold-span coverage and semantic sufficiency are separate measures. Family-paired intervals retain dependent repeated observations; cases from the same upstream projects may remain correlated.

No final score, stability result or semantic-audit total is claimed yet. The final report will retain failures, resource costs, strict/audit disagreements and concrete examples rather than select the most favorable result.

## Inspect and reproduce

- [Main data card](data-card.md), [experiment protocol](protocol.md), [main promotion receipt](final-20261020/main-promotion.json)
- [Development records and fixed-source replay](completion-dev-20261020/README.md), [single-factor experiment and replay](ablation-20261020/README.md)
- [Original pilot review](annotation-review/README.md), [new independent reviews](../../datasets/v2/realistic-draft/review-evidence/README.md), [human queue](human-review.md)
- [Historical v1 report](../2026-10-15/README.md), [fixed-source replay checks](baseline-checks.json)
- [Earlier partial pilot](pilot-resume-20261020.md), [staged recovery](pilot-recovery-20261020.md); their 63/150 historical counter is preserved separately
- [AI use/workflow](../../AI_used.md), [code walkthrough](../../docs/code-walkthrough.zh-CN.md), [interview exercises](../../docs/interview-self-check.zh-CN.md)

The [final fresh installation](final-offline-verification.json) passed 861 tests, lint and main validation with locked dependencies in a new environment. [Real long-development-input consumers](final-consumer-verification.json) passed HTTP success → safe rejection → recovery and byte-identical CLI report replay without inference. The earlier 510-test [offline receipt](verification.json) and [model-error-stop review](model-error-stop-verification.json) remain valid only for their stated code/inputs. Optional Jev smoke records remain supplementary and do not establish calibration or a cost/speed advantage.
