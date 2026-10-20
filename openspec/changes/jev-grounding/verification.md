# Architecture checkpoint — 2026-10-20

Historical status: research and planning complete; implementation had not started and all nine tasks were unchecked. No provider inference, credential change, source-code change or historical-run rewrite occurred in that checkpoint. Current implementation acceptance is recorded below.

This section records the planning checkpoint at commit `45118ac`. Implementation started after the user invoked `ms-session-loop`; subsequent budget-policy clarification rejects unsupported hard dollar caps and keeps total/per-provider attempt caps explicit. The reviewed hashes below describe that historical planning revision, not a claim that later edited files have the same bytes. Runtime acceptance will be recorded separately below after actual integration.

- Official documentation and fixed SDK source were reviewed by the parent and a separate `gpt-6.1-sol` / `max` research agent. See the [public source note](../../../docs/research/jev/README.md).
- Non-author design/spec review found two substantive issues: parser tolerance could weaken confidence gates, and wording could let quote-only checks borrow unquoted context. Both were corrected and the reviewer reread the saved files; no further substantive issue remained within that narrow scope.
- The accepted design keeps raw and locally derived confidence distinct, gates on their minimum, and separates final full-context verdicts from quote-only auxiliary checks. Fallback does not recursively re-enter Jev.
- Reviewed SHA-256: design `2415bab541faa2e471de7374e970e69f68b16a65551f9b0924a333cd18047404`; spec `72e08cec7e5730d15b35aa4eefdf8f5bbdef71b3e5d566ba4525804ac92e46b6`.
- `openspec validate jev-grounding --strict` exited 0. Planning status reports four required artifacts present; this is not runtime completion. Relative Markdown links and whitespace were checked.
- Runtime tests and local logging probes are not applicable to this documentation-only checkpoint. Future implementation must perform the listed consumer, failure and independent logging checks; earlier tests do not establish Jev behavior.

Pending: optional adapter/consumer implementation, mixed-provider records, offline acceptance, local TypeSafe credentials, explicit LLM configuration and a new live budget, then real smoke and development calibration. The prior stopped Codex pilot remains at 63/150 attempts; its unused allowance is not spent here.

## Implementation acceptance — 2026-10-20

The original provider, service and evaluator owners implemented the new paths under separate file boundaries. The parent owns shared configuration/contracts and integration. All checks below use synthetic provider responses; no Jev or LLM inference, authorization refresh, credential modification or pilot resumption occurred. Real compatibility, calibration and performance remain unverified.

| Scope | Actual author verification |
| --- | --- |
| Shared contracts and opt-in configuration | 52 focused checks and lint passed after correcting unused Jev environment parsing. |
| Native adapter | 143 focused checks passed after 18 new regressions reproduced duplicate-key usage loss on the prior adapter. Six local native/consumer calls exercised success, protocol rejection and recovery; all six streams closed, and both consumer failures retained the unambiguous 317/29 synthetic token counts. Final adapter SHA: `ddca4ef05ef6d5584332b787bc4a99d3f9246111bf4269581becc4987406dc6e`. |
| Service and both HTTP methods | 161 focused checks passed. Actual ASGI requests through native Jev/OpenAI adapters and HTTPX substitutes returned 200, 200, 504, 502, 200 for success, escalation, escalation timeout, malformed confidence and recovery. The 44 safe diagnostic records retained correlation and stage/error classification without injected content or keys. |
| Mixed-provider evaluator | 186 checks passed. Actual CLI runs covered both methods/tracks, success, escalation failure, malformed response, recovery, quiet logging and unsupported hard-dollar-cap rejection before calls. Report and development threshold replay left all saved artifacts unchanged. |
| Historical integrity | Four v1 runs replayed with their fixed source, returning 2/0/0/0; the format-2 original pilot replay retained its failure and exit 2. Copied artifacts stayed byte-identical, and all 258 protected dataset/report files were unchanged. |

Reproducible repository tests live in `tests/provider/test_jev_provider.py`, `tests/service/test_jev_*.py`, `tests/test_jev_contracts.py` and `tests/evaluation/test_hybrid.py`. The two CLI fixture drivers substitute only external/provider boundaries; they are test helpers, not product modes. Tests explicitly mark saved measurements as offline fixtures.

Non-author review independently reproduced a configuration regression: invalid unused Jev model/threshold settings blocked original methods. The parent repaired conditional parsing while retaining explicit CLI/factory validation. The reviewer then passed 91 probes and 55 targeted tests, with the original failing evidence preserved. The accepted configuration SHA is `efe9880e6f6691702c764654344532af21b39d252dd4392bb69fbc14eb612d81`.

The same reviewer found a second defect: nested duplicate answer/probability keys correctly caused rejection but also discarded unique valid top-level usage. The provider owner repaired this with a single decode that discards every value for an ambiguous key, preserves other strictly validated fields, and still rejects the entire response. Duplicate usage/model fields are never resolved by picking a convenient value. Independent repair verification passed 84 checks across 14 native requests; all response streams closed and the original failing evidence remained unchanged.

Final non-author consumer acceptance passed against the corrected adapter and unchanged service/evaluator source:

- Actual ASGI `/verify`: 15 normal scenarios / 119 checks, plus a separate broken-stderr-pipe process with three scenarios / 28 checks. The probes cover both extraction paths, question-local quote-only scope, disabled fallback, budget/deadline/cancellation and success → escalation timeout → recovery. Both processes exited 0.
- Actual CLI: six fresh subprocesses across both methods exercised run, report and development sweep. Each run preserved OK → ERROR → OK, all gold and non-supported denominators, stage usage, known Jev cost subtotal and unknown mixed total. Run/report correctly exited 2 for the retained failure; sweeps exited 0 without provider calls. All 65 checks passed; records/config/cases/completion remained byte-identical across replay.
- Diagnostics: 124 service records and 71 CLI-run records passed field, correlation, lifecycle and injected-secret checks. An overly broad reviewer assertion initially mistook the safe error code `confidence_unresolved` for a leaked confidence field; the assertion was corrected without changing product behavior or rerunning the successful consumer commands. Broken writes are covered; permanently blocked synchronous sinks are not certified.

This completes the bounded offline acceptance in tasks 1.1–4.1. It does not close real-provider tasks 4.2–4.3 or the older Codex/auth independent-review limitation.

The parent ran the whole repository suite in a temporary working directory with provider environment variables removed: **773 passed in 227.03s**, lint exit 0, tested source unchanged during execution. That baseline preceded the duplicate-key correction. Only the adapter and its test file subsequently changed; the 143 focused checks above cover the affected path. The environment was the existing locked Python 3.11 environment, not a new clean installation. Strict OpenSpec validation, development/diagnostic dataset validation and eight changed Markdown files' local links also passed. These are separate evidence scopes, not a claim that the pre-repair full suite ran against the final adapter.

The spending contract enforces total and per-provider attempt allowances, with conservative reservations. The exact supported monetary policy is `measured_only_no_hard_limit`: known usage can be priced from a matching dated snapshot, while subscription or missing usage leaves the total unknown. No local byte estimate is presented as a guaranteed token or dollar ceiling.

Pending live stages require a locally configured TypeSafe key, an explicit extraction/fallback LLM identity, and a new approved experiment budget. The initial 0.8 thresholds are uncalibrated. No historical held-out inputs, gold aliases or original prompt bytes were adjusted to favor Jev.
