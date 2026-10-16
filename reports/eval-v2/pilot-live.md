# Development pilot: quota-blocked live run

**Status: blocked.** On 2026-10-16, Robin authorized at most **60 Codex / `gpt-6.1-sol` provider attempts**, counting retries and repairs. The first model request returned `quota_exhausted`. The runner stopped subsequent model jobs, retained every requested job and finished the heuristic jobs. Robin confirmed that quota had not recovered and requested preservation of the records. No further inference was attempted.

The [pre-inference plan](pilot-live-plan.json) binds the reviewed 12-case / 126-claim development input, settings, source/prompt/scorer hashes, seed, job order and stop rules. The baseline is commit `3df1bf1bfaa48b06fb0219bca8de58d4dc4cf5ec`; runtime and dataset fingerprints remained unchanged. No future test input was generated or measured.

| Observation | Saved result |
| --- | --- |
| Requested matrix | 12 dev cases × 3 methods × 2 tracks = 72 jobs; one repetition |
| Actual provider attempts | **1**, with 0 retries and 0 repairs |
| Remaining approved allowance | **59**; a later run must not reset it to 60 |
| First model job | `v2-dev-p01`, optimized, end-to-end, ERROR / `quota_exhausted` |
| Other model jobs | 47 NOT_RUN / `quota_exhausted`; no provider attempts |
| Heuristic jobs | 24 OK; quality scores equal the earlier offline pilot |
| Successful LLM predictions | **0**; no response-model identity returned |
| Usage and subscription cost | **Unknown**, not zero; the attempted request has incomplete usage |
| Failed operation latency | 3,804.36 ms, including authentication work; no successful-model latency sample |
| Runner outcome | `COMPLETED_WITH_ERRORS`, exit 2; no cleanup error or source drift |

The actual attempt started at `2026-10-16T18:34:14.180188Z`. Safe local diagnostics show successful credential renewal before the quota failure. The provider distinguishes explicit quota error codes from generic rate limiting; this observation does not establish an account-wide balance or reset time. Credentials and raw authentication responses are excluded from the saved evaluation.

The [records](pilot-live/records.jsonl), [configuration](pilot-live/config.json), [summary](pilot-live/summary.json), [completion record](pilot-live/completion.json) and [accounting receipt](pilot-live-receipt.json) retain the complete population. Every method/track keeps all 126 gold claims in failure-inclusive scoring. Its zero scores or degenerate intervals for unavailable model outputs describe failure accounting, **not measured model accuracy**. The 47 NOT_RUN records are consequences of the shared stop, not 47 additional upstream failures. Annotation, extraction, judgment and evidence error analysis cannot be inferred from this run.

The actual CLI invocation is recorded in the receipt. Offline replay needs no model call:

```bash
uv run grounding-eval report reports/eval-v2/pilot-live
```

Exit **2** is expected because the original failures are preserved. Replay reproduced all 23 saved run files byte-for-byte. The original clean-environment 510-test and HTTP/CLI acceptance remains applicable to the unchanged runtime; it was not repeated or relabeled as a new live success.

The per-operation limit remains six attempts, provider timeout 30 seconds and operation timeout 60 seconds. Requested output tokens are 8,192; Codex does not apply that cap and the effective limit is unknown. The runner requires the six-attempt reservation to fit before starting each model job, so remaining allowance does not guarantee a complete matrix.

Continuation requires quota recovery. Use a new output directory, preserve this failed run, keep the agreed provider/model and charge every subsequent attempt against the remaining 59. There is no automatic retry or scheduled background run. A single rejected request cannot support an empirical full-matrix token, latency or cost budget; that estimate, controlled ablation and final held-out comparison remain pending successful pilot observations and later budget authorization. `datasets/main.jsonl` remains v1. This checkpoint is a local commit, with no new public push.
