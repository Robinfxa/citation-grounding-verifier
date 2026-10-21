# Live development pilot continuation — 2026-10-20

**Outcome: completed with errors, not a completed method comparison.** Robin resumed real testing. The application-owned default authorization refreshed successfully and the model catalog contained `gpt-6.1-sol`. The unchanged runtime, prompts, source data, model settings and seeded 72-job matrix were bound by a [plan saved before inference](pilot-resume-20261020-plan.json). The run used the remaining 59-attempt allowance, in a new directory, without replacing the [original quota-blocked run](pilot-live.md).

## Actual outcome and resources

| Method / track | OK | ERROR | NOT_RUN | Attempts |
| --- | ---: | ---: | ---: | ---: |
| Heuristic / oracle | 12 | 0 | 0 | 0 |
| Heuristic / end-to-end | 12 | 0 | 0 | 0 |
| Minimal / oracle | 2 | 7 | 3 | 16 |
| Minimal / end-to-end | 2 | 7 | 3 | 16 |
| Optimized / oracle | 0 | 6 | 6 | 12 |
| Optimized / end-to-end | 1 | 4 | 7 | 10 |

The 24 model errors are 2 `upstream_timeout` and 22 `upstream_unavailable`. All 19 uncalled model jobs have `attempt_budget_exhausted`. The 54 attempts include 23 retries and no repairs. Added to the previous 1 attempt, the original allowance reached **55/60**, leaving 5—insufficient for the existing six-attempt reservation. The runner exited **2**, with no source drift or cleanup error. The safe unavailable category does not identify the underlying network/server/account cause, and is not reclassified as quota exhaustion. A late successful retry shows that failures were not universal throughout the run.

Every method/track retains all 12 requested cases and 126 gold claims. The machine report keeps failure-inclusive strict scores; unequal successful populations make both paired method comparisons **NOT_RUN**. Those failure-dominated scores do not establish comparative semantic accuracy. The heuristic reproduced its prior observations.

Known token subtotals are **17,017 input / 5,087 output**, but **25 attempted model jobs have incomplete usage**, including one successful job with an unmetered failed retry. Total usage and subscription dollar cost remain **unknown**, not zero. Returned model identities on successful responses are `gpt-6.1-sol`. The five successful jobs span four distinct cases; they took 14.69–34.80 seconds each (median 16.05 seconds). This selected, small population is not a reliable full-matrix latency forecast.

## What the successful outputs reveal

The two successful minimal/oracle jobs judged p01's 8 and p05's 10 gold claims with the correct labels. Their strict evidence coverage was respectively 3/8 and 0/10; oracle evidence semantics were not independently audited in this checkpoint. The three successful end-to-end outputs were reviewed by a separate gpt-6.1-sol/max coding agent, with all gold and predictions visible. This is **exploratory development attribution, not a blinded test audit or a semantic aggregate score**.

- **Surface alignment loss:** p01-c03 differs only by `also`. It is a strict mismatch despite preserved meaning and the necessary cross-passage links.
- **Real atomicity failure:** p06's size and hash properties are merged into one predicted assertion. Both contents are present, but two gold facts cannot silently receive full credit from one non-atomic prediction.
- **Real quotation gaps:** p02 predictions omit the governing False/legacy transaction conditions from citations; p06 examples omit the `metadata()` or `files()` API link.
- **Evidence-proxy undercounting:** two p06 quotations fully convey the asserted behavior but omit nonessential connectors or a PEP suffix from the frozen gold span. Other short-quote/entity cases remain uncertain.

The [qualitative review](pilot-resume-20261020-dev-review.md) and [item-level evidence](pilot-resume-20261020-dev-review.json) retain these distinctions. No gold label, alias, scorer or prompt was changed to improve scores. The smallest candidate for a later separately budgeted experiment is to add only the subject/API-and-condition quotation requirement to `MINIMAL`; `JUDGE` already contains it. Atomicity changes would be a different factor and must not be bundled. This hypothesis has not been tested or adopted.

## Integrity and next step

A [non-author integrity review](pilot-resume-20261020-review.json) checked the frozen plan, complete population, cumulative allowance and usage uncertainty. Guarded offline replay through the actual CLI exited 2 as expected and preserved all 23 artifacts byte-for-byte, with zero network/provider/authentication/credential attempts. Its 238 checks are audit assertions, not additional product unit tests or semantic validation. The [receipt](pilot-resume-20261020-receipt.json) binds the command, exit, runtime, data and artifact hashes. Raw records and reports are in [the saved run](pilot-resume-20261020/summary.json).

The run exposed a budget-efficiency gap: per-job retry limits do not stop the next job after repeated upstream failures. An optional fail-fast policy is being implemented and independently checked before more inference. Robin has approved [90 additional attempts and a staged recovery plan](pilot-recovery-budget.md): cumulative ceiling 150, balance 95 at approval; two fixed availability checks first, then the original full pilot only if both succeed. Stop on the first model failure. These future calls do not erase this run or reset its budget. Final data expansion/freeze, controlled ablation, held-out/repeat inference and the preselected semantic test audit remain incomplete.
