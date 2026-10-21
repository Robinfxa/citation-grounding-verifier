# Proposed pilot recovery allowance — 2026-10-20

Status: **authorized by Robin on 2026-10-20**. Robin approved the additional 90 attempts and the staged plan below. The cumulative pilot ceiling is now 150, with 55 already used and 95 remaining at approval. This does not erase earlier consumption or authorize final test inference.

The original quota-blocked run used 1 attempt. The [continuation](pilot-resume-20261020/summary.json) used 54 attempts, including 23 retries and no repairs: 5 model jobs succeeded, 24 failed and 19 were not called. Cumulative use is 55/60; the remaining 5 cannot cover the existing six-attempt reservation. Authentication refresh/model discovery succeeded, but do not establish inference reliability. The root cause of the safe `upstream_unavailable` errors is not established by the retained diagnostics.

## Approved increment

Increase the **cumulative pilot ceiling from 60 to 150 attempts**: 90 additional attempts, leaving 95 available after the two preserved runs. Retries, repairs and unknown-stat reservations count. No model/provider/account change is proposed. Dollar cost remains unknown for subscription use.

Before any further call, complete offline acceptance of the opt-in `--stop-on-model-error` guard and freeze its code/configuration. The guard retains every planned job and its denominator, continues heuristic jobs, and stops further model calls on the first model error. It does not change prompts, transport, timeouts, schema gates or scoring.

1. **Recovery check:** at most 12 attempts across two sequential one-job CLI runs: minimal/oracle on p01, then minimal/end-to-end on p06. These are deliberately previously successful development cases to check availability, not an accuracy sample. Stop this stage on any failure. Keep both outcomes, including a failed result; do not run repeated probes until success.
2. **Pilot comparison:** only if both recovery checks succeed, run the unchanged 12-case, three-method, two-track matrix in the original seeded order with the new fail-fast flag. The run allowance is the remaining cumulative balance, not a fresh 95. Stop on the first model error or reservation shortage. Retain the preceding incomplete runs separately; do not pick the best result per case or pool duplicates as independent cases.
3. **Analysis:** independently replay, attribute development failures, and produce the subsequent ablation/final-matrix estimate. Further calls require their own explicit ceiling.

The ideal full pilot requires about 60 model attempts before failures/repairs. The five successful jobs observed here took 14.69–34.80 seconds per job and returned 16,530 input / 4,612 output tokens in known completed responses. One of those jobs had an unmetered failed retry, so these values are not complete costs. Only four distinct cases and one optimized output succeeded; these observations do not justify a precise full-matrix price or latency forecast. The new allowance is a bounded recovery reserve, not a promise to spend it all or to complete the full evaluation.

The final proposed 48-case test comparison plus two additional 16-case repeats would require about 400 ideal model calls (48×5 + 2×16×5), before development ablation, failures and retries. That matrix is **not approved or frozen**. A usable pilot comparison and resolved measurement issues must precede final dataset expansion/freeze and a defensible budget decision.
