# Jev experimental verification

The optional TypeSafe integration separates claim extraction from typed decisions:

| Approach | Claims from an answer | Judgment and escalation |
| --- | --- | --- |
| `jev_minimal` | Existing deterministic sentence rules | Jev, followed by LLM review when required |
| `jev_optimized` | Answer-only LLM atomic extraction with exact answer anchors | The same Jev and LLM-review policy |

The original `minimal` remains the default. Its one-call generative LLM method is different from `jev_minimal`. A rule-produced sentence can contain multiple claims; evaluation continues to penalize merged, missing and extra claims. In the oracle track both Jev methods skip extraction and use the same algorithm.

This integration is experimental. Offline acceptance can establish request construction, control flow and deterministic validators. It does not establish live Jev compatibility, calibrated confidence, grounding accuracy or a speed/cost advantage. See the [current verification status](../openspec/changes/jev-grounding/verification.md).

## Local configuration

Copy the relevant values into the project's ignored `.env`; never put a real key in `.env.example`, a report or a chat message.

```dotenv
GROUNDING_APPROACH=jev_minimal
TYPESAFE_MODEL=jev-1.14.0
TYPESAFE_API_KEY=your-local-key
GROUNDING_JEV_FALLBACK=true
GROUNDING_JEV_LABEL_THRESHOLD=0.8
GROUNDING_JEV_EVIDENCE_THRESHOLD=0.8
GROUNDING_JEV_REASON_THRESHOLD=0.8
```

Use `jev_optimized` to select LLM extraction. The existing `GROUNDING_PROVIDER`, `GROUNDING_MODEL` and provider-specific configuration select the generative LLM for extraction and review; they do not select Jev. Retain an explicitly configured, available LLM using the [existing setup](../README.md). TypeSafe's key is independent of the LLM credential or this application's Codex authorization. Moving Jev aliases are rejected so an experiment cannot change model version silently.

Fallback is enabled by default for the new methods. With it enabled, configure the LLM before making requests. For an explicit Jev-only abstention experiment, `GROUNDING_JEV_FALLBACK=false` disables escalation: an uncertain result then fails with `confidence_unresolved`. Optimized still requires an LLM for extraction even when fallback is disabled. There is no automatic switch to rule extraction after an extractor failure.

The service continues to use `POST /verify` with `context_passages` and `generated_answer`. Its successful response fields remain unchanged; detailed confidence and provider accounting belong to evaluation artifacts rather than the public response. Start the service using the existing README instructions only when the configured providers and intended calls are authorized.

## Evidence and uncertainty

Jev chooses from fixed options; it does not generate arbitrary claims, quotations or explanations. The fast path judges against the complete supplied context, selects a bounded bundle of verbatim source windows and separately checks whether those quotations establish the full claim. Quotes are reconstructed from source offsets and checked as exact Unicode substrings. Two passages can contribute joint evidence. Candidate retrieval is deliberately limited; it does not justify declaring the complete context unsupported.

Low label/reason confidence, a missing candidate or insufficient/disagreeing quoted evidence routes the affected fixed claim IDs to one LLM judgment batch over the full context. That LLM receives no Jev candidate labels to endorse. It cannot silently change, drop or duplicate the claims. A failed review fails the whole request, while the evaluator retains every requested gold claim in the appropriate denominator. Transport, authentication and malformed-response errors remain operational errors and do not trigger a hidden provider switch.

Jev's confidence is a statistic of its option probabilities, not a probability that the answer is correct. Each gate uses the smaller of the reported confidence and the documented formula computed from the raw distribution; parser tolerance cannot promote a below-threshold decision. The initial 0.8 thresholds are uncalibrated experimental values. Scores from separate questions are not multiplied, and LLM-reviewed results receive no invented Jev confidence. Jev-path explanations are disclosed templates, not generated reasoning traces.

Source windows may miss paraphrases, long conditions or complex evidence chains. Confident semantic mistakes remain possible after both Jev checks. Threshold development must use development data; freeze policy/model identities before a later held-out comparison. The [research note](research/jev/README.md) links the official evidence and its limits.

## Evaluation and replay

Select the new saved-record format explicitly with `--format-version 3`. Jev runs also require `--provider-budgets` and the existing total-attempt allowance. A budget file has this shape; the zero values below intentionally authorize no inference. Replace them only with the approved allocations for a new experiment, and use `openai` instead of `codex` when that is the configured LLM provider.

```json
{
  "provider_attempts": {"typesafe": 0, "codex": 0},
  "dollar_policy": "measured_only_no_hard_limit"
}
```

After providers, case selection and budget are agreed, save that allocation as `jev-budget.json`, save the selected development IDs as a JSON array, and run:

```bash
uv run grounding-eval run --dataset datasets/v2/pilot.jsonl \
  --approaches jev_minimal,jev_optimized --format-version 3 \
  --split dev --track both --case-ids-file jev-case-ids.json \
  --provider-budgets jev-budget.json --stop-on-model-error \
  --max-total-provider-attempts "${EVAL_ATTEMPTS:?Set the new approved total allowance}" \
  --output reports/runs/jev-dev
uv run grounding-eval report reports/runs/jev-dev
uv run grounding-eval sweep reports/runs/jev-dev --thresholds 0.7,0.8,0.9
```

Use a fresh output directory. The CLI loads Jev settings when either Jev method is selected, even if the service's default approach is `minimal`. Each operation reserves its maximum attempts against the total and relevant provider allocations before starting; a reservation shortage leaves explicit NOT_RUN records with all gold facts retained. Allocation caps are conservative and may stop a run with some allowance unused.

`report` and `sweep` read saved artifacts without inference. Sweeps are development-only, vary the three gates together, and describe only decisions actually observed. They do not invent missing quote checks, fallback outputs, counterfactual cost or a new whole-pipeline score. Existing v1/v2 artifacts retain their formats and fixed-source replay requirements.

The first live increment was authorized on 2026-10-20: development case `v2-dev-p01`, once per Jev method on the end-to-end track, using Codex / `gpt-6.1-sol` for extraction and fallback. Its shared ceiling was 12 attempts, with six per operation, 12 allocated to each provider within the shared ceiling, transport retries disabled and stop-on-model-error enabled. The saved seeded order selected Optimized first. Codex extraction succeeded, then Jev returned `jev-1.14.0` and measured usage but failed response validation with `provider_protocol_error`. Minimal was left NOT_RUN. The [saved run](../reports/jev/smoke-20261020/run-01/summary.json) used two attempts, with no retries or repairs; ten remain unspent after the stop. That unused allowance does not override the stop condition or authorize diagnosis calls. No successful Jev workflow, confidence calibration or speed/cost benefit has been established. A failed stage's latency is not a successful-verification benchmark; broader diagnostics and calibration remain separate.

The diagnostic follow-up adds a fixed `protocol_reason` label to opt-in local logs for post-decode Jev validation failures. It records the first rejected check, without question IDs, choices, probability values or response bodies. Validation thresholds, returned errors, usage and routing are unchanged. It can help diagnose a later request; it cannot reconstruct the first run's missing response or establish that its cause is fixed.

Robin explicitly approved that continuation on 2026-10-20. It froze commit `6feda7b09eac9566d63804d3b53133f73b4d3c06` and the same two methods/case/track, models, seed `20261015`, thresholds `0.8`, fallback enabled, 30-second provider and 60-second operation deadlines. The fresh [continuation](../reports/jev/resume-20261020/README.md) used a shared ceiling of ten, each provider allocation ten within that ceiling, six per operation, zero retries and stop-on-model-error. Optimized again ran first: extraction succeeded, then Jev failed at the fixed `probability_sum` check. Minimal was NOT_RUN. Actual continuation consumption was two attempts; combined with the first smoke, **4/12 have been used and eight remain unspent**. The new stop prevents automatic further calls. Costs remain unknown without matching pricing; repeated outputs are not combined by choosing the best result.

The [official Choice contract](https://docs.typesafe.ai/primitives/choice) describes probabilities across all options summing to one. This implementation allows an absolute sum deviation of `0.001`; the continuation failed that check. Raw rejected values were not retained, so the amount, direction, question identity and whether the cause was precision or an abnormal distribution remain unknown. No evidence currently justifies changing the tolerance or renormalizing the response. The first smoke's unspecific error cannot retroactively be assigned this reason.

## Resource and privacy boundaries

All extraction, Jev, review, repair and retry attempts share one operation deadline and total attempt cap. Several Choice questions can be sent in one request; question count and provider-attempt count are separate measures. Two Jev rounds, LLM extraction and any fallback all contribute to elapsed time and cost.

`GROUNDING_JEV_MAX_REQUEST_BYTES=256000` and `GROUNDING_JEV_MAX_QUESTION_BYTES=128000` limit serialized UTF-8 data locally. The latter includes shared state plus one question. These byte bounds are not estimates of provider token limits. Oversized input fails explicitly; the adapter never silently trims context or enables the long-context preview.

Evaluation records identify each stage's provider, model and measured usage. A dated matching price snapshot can price known Jev usage; missing usage or an unpriced subscription stage leaves the total dollar cost unknown, with any known subtotal shown separately. The supported spending policy enforces attempt caps. It does not guarantee a monetary ceiling, and unsupported hard-dollar-limit requests are rejected before inference. A previous experiment's unused allowance is not a new experiment's authorization.

Routine local diagnostics contain safe stages, outcomes, routing reasons and counts. They omit source text, answers, quotes, keys and raw upstream error messages. Detailed decision traces are saved only as requested evaluation output. Local logging does not install telemetry or establish a timeout guarantee for a permanently blocked synchronous log sink.
