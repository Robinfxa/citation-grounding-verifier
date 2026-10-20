# Evaluation v2 — development pilot checkpoint

**Status: recovery checks passed; full pilot stopped on its first model error.** The [staged recovery](pilot-recovery-20261020.md) used eight attempts: the two fixed checks each succeeded once; the original full matrix then recorded 24 heuristic successes, three model successes, one judgment-stage timeout and 44 uncalled model jobs. Both paired comparisons remain NOT_RUN. Cumulative pilot use is **63/150**, leaving **87 unspent** under the [approved plan](pilot-recovery-budget.md). No further inference occurred after the stop. The [earlier continuation](pilot-resume-20261020.md) remains separately preserved.

The original benchmark's short fictional answers did not establish real-document performance. This round prepares 12 development cases / 126 facts over licensed documentation, non-author annotation review and versioned measurement tools. It preserves the old results rather than relabeling them as new evidence. `datasets/main.jsonl` is still v1; the proposed 72-case final population has not been built or frozen.

## Evidence available now

| Feedback or requirement | Artifact | Evidence and boundary |
| --- | --- | --- |
| Denser real-source tasks | [Data card](data-card.md); [source research](../../docs/research/eval-v2-sources.md) | 12 development cases, frozen licensed documentation, exact source/answer mappings; no production-response sample |
| Annotation reliability before measuring | [Locked independent judgments and disagreements](annotation-review/README.md) | Non-author AI review before author-label exposure, retained disagreements; human review pending |
| Distinct measurement layers | [Scorer calibration](../../tests/evaluation/fixtures/measurement-calibration.md); [audit policy](audit-policy.md) | Deterministic strict scoring plus separate two-stage audit tools; no final test audit yet |
| Reproducible engineering | [Offline verification](verification.json) | 510 tests and lint, actual long-input HTTP/CLI success/failure/recovery, protected snapshots and failure denominators; this receipt predates the fail-fast increment |
| Current run integrity | [Independent review](pilot-recovery-20261020-review.json) | Three guarded CLI replays, exit 0/0/2, all 69 artifacts byte-identical; no inference |
| Current recovery outcome | [Staged report](pilot-recovery-20261020.md); [receipt](pilot-recovery-20261020-receipt.json) | Two checks succeeded; full matrix stopped at first model error; no complete paired comparison |
| Model-error stop acceptance | [Verification](model-error-stop-verification.json) | 93 related regressions and separate 78-assertion independent CLI review; no model-quality inference |
| Earlier model observations | [Continuation report](pilot-resume-20261020.md); [saved records](pilot-resume-20261020/records.jsonl) | 5 successful jobs, 24 model errors, 19 model jobs uncalled; operationally incomplete |
| Checkable run integrity | [Independent review](pilot-resume-20261020-review.json); [receipt](pilot-resume-20261020-receipt.json) | 72-record population and allowance verified; guarded CLI replay exit 2, all 23 files byte-identical |
| Useful error attribution | [Development review](pilot-resume-20261020-dev-review.md) | All three successful end-to-end outputs reviewed; distinguishes strict misses, atomicity and evidence gaps; no semantic aggregate score |
| Historical reproducibility | [Baseline checks](baseline-checks.json) | Fixed baseline installed in isolation; four old reports reproduced byte-for-byte |
| Controlled optimization | [Protocol](protocol.md) | Candidate quotation rule motivated by dev observations; no controlled experiment performed or improvement claimed |
| Author understanding | [Walkthrough](../../docs/code-walkthrough.zh-CN.md), [questions/exercises](../../docs/interview-self-check.zh-CN.md), [human checklist](human-review.md), [AI use](../../AI_used.md) | Materials prepared; Robin's own review and demonstrated understanding remain pending |

## What the current results show

The following observations describe the earlier continuation, not pooled results across attempts. The heuristic completed both tracks on all 12 cases. Its oracle macro F1 is 0.0365 and end-to-end strict joint-label F1 is 0.0614. Oracle labels were correct for 7/126 claims and frozen evidence was covered for 1/120 non-U claims. These observations expose the lexical baseline's limits; they do not establish LLM difficulty.

The two successful minimal/oracle jobs correctly labeled 18 supplied claims in total. The successful end-to-end jobs were optimized/p01 and minimal/p02,p06. They are a small, availability-selected development population, not a complete paired comparison. All failures retain their requested cases and gold claims in the [machine report](pilot-resume-20261020/summary.json); its failure-inclusive scores must not be promoted to a claim of comparative semantic accuracy.

Non-author qualitative review found both harmless surface mismatches and actual shortcomings. Removing `also` caused one strict miss; two independent properties were merged into one prediction; some citations omitted their governing API or mode condition. Other quotations sufficiently conveyed a fact but missed nonessential text in the frozen gold span. No labels, aliases or scorer were adjusted after viewing these outputs. The review was not blinded and does not replace the preselected final test audit.

The continuation used 54 attempts, including 23 retries and no repairs. Known usage is 17,017 input / 5,087 output tokens, but 25 attempted jobs have incomplete usage, so total consumption and subscription cost remain unknown. Successful outputs report `gpt-6.1-sol`. Provider timeout was 30 s, operation timeout 60 s, per-operation attempt ceiling 6; requested output limit 8,192 tokens is **not applied on Codex**, with the effective limit unknown. See the run report for outcome counts and successful-job timing.

Strict scorer version is `2`; schema, dataset and run formats are separate. Exact quotation validity, frozen gold-span coverage and semantic evidence sufficiency remain distinct. AI author/reviewer agreement cannot prove annotation truth, and public-source pretraining contamination remains possible.

## Reproduce and continue

The root [README](../../README.md) provides frozen installation, explicit pilot CLI/HTTP commands, bounded model-run syntax and isolated historical replay. The earlier continuation can be reconstructed without inference with `uv run grounding-eval report reports/eval-v2/pilot-resume-20261020`; exit 2 preserves its operational failures. Never overwrite a run directory.

The approved staged sequence has reached its failure stop. The new model-error guard passed independent offline acceptance, both recovery checks succeeded, and the full matrix stopped at the first model timeout. Further calls need an explicitly agreed continuation; the unused allowance does not override that stop rule. Final expansion and split acceptance, one-factor development ablation, final test/repeat inference and the preselected semantic audit remain incomplete. Later experiment budgets are separate from the pilot allowance.

The pilot contains 0 natural responses, 6 AI-generated-from-source answers and 6 controlled mutations, from 12 document families in three software projects. It does not establish representative production performance or all proposed final difficulty quotas. No final dataset freeze, new complete model comparison, prompt improvement, human review or CI result is claimed here.
