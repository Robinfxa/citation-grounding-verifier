# Recorded experiments — 2026-10-15

These are actual verifier calls, including live Codex / `gpt-6.1-sol` inference. They are separate from offline engineering fixtures. Each run stores its selected cases, immutable request records, configuration, source/prompt fingerprints, completion state and a reproducible summary. Only synthetic benchmark content and nonsecret settings are included; authorization files and raw diagnostic logs are excluded.

## Conditions

All methods receive the same selected cases. Jobs are shuffled with seed `20261015`, executed sequentially with no warmup, and use one verifier instance per approach. Minimal and optimized share the model, account profile, transport limits and exact-citation validation. The optimized end-to-end path normally makes two calls; its oracle track skips extraction. Retries, repairs and failed requests count toward latency and known usage.

Latency is full local verification wall time, including network and validation, measured on macOS / Python 3.11.9. No concurrency load or repeated-trial model variance is measured. The Codex route omits unsupported sampling and output-token request controls; the configuration records the shared settings, and the adapter enforces local stream/operation bounds. The provider's model slug is recorded, not a pinned immutable model snapshot. Subscription usage has no inferred dollar price; a token count is not an estimate of remaining plan quota.

End-to-end **joint label F1** is `2 × correctly aligned and labeled claims / (gold claims + predicted claims)`. Strict decomposition F1 uses aligned claims regardless of label. Unmatched valid paraphrases are penalized by the frozen text/alias matcher. Oracle results isolate labeling on the same supplied claims. Evidence coverage requires an allowed complete gold evidence set; this is a conservative span proxy, not an independent semantic entailment assessment. Case exactness requires complete claim alignment, correct verdicts, sufficient gold evidence, and every returned quotation to be literal and gold-relevant. Request failures remain in the denominators.

Confidence intervals use 10,000 seeded family bootstrap draws. Every case here has a distinct family, so this is case resampling. Paired intervals compare the same sampled families. Intervals describe sample sensitivity; they omit annotation bias, model randomness and production distribution shift. Undefined and degenerate bootstrap draws remain visible in the JSON summary.

## Development v1 and the revision decision

[Development v1](development-v1/summary.json) used implementation commit `8573ea4` and the original 66-claim main dataset (`90d760c1…`; 17 development claims). It completed all 48 jobs, with **45 OK and 3 protocol errors**. The source did not change during the run. All three errors arose on the development `zelko-port` case; those records and their unknown-usage fields remain unchanged.

| End-to-end, eight development cases | Joint label F1 | Gold evidence coverage | Exact cases | Median / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Heuristic | 0.6250 | 0.3636 | 3/8 | 0.425 / 9.098 |
| Minimal LLM | 0.8750 | 0.8182 | 5/8 | 4,845 / 5,456 |
| Optimized LLM | 0.9714 | 0.9091 | 6/8 | 8,015 / 10,292 |

Three different findings drove the revision:

1. **Evidence specificity.** Optimized correctly judged the Kelm retention claim, but quoted only “It retains the newest two manifests.” The frozen evidence annotation includes the preceding entity sentence. The revised judge gives a general rule to retain an antecedent and governing conditions in compact sufficient quotations, with an unrelated multi-entity example. Extraction and both minimal prompts remain unchanged.
2. **An annotation omission.** Optimized extracted an additional cache-use assertion from the Diska causal sentence. A source-only independent review confirmed it was legitimate and found the analogous omission in Virel. The original author added one unsupported cause-occurrence fact to each case, without changing prior claims, aliases or inputs. The corrected dataset has 68 claims (18 dev / 50 test), hash `c9a30acf3ddb3093514a89831f7ae1d2be336f02df1d7b9143b1a01719aec1be`, and passed targeted independent review before any held-out output inspection. See [annotation history](../../docs/dataset-review.md).
3. **A transport compatibility defect.** A post-run diagnostic using the ordinary verifier found completed reasoning items that omitted their optional status. The adapter incorrectly rejected them. The repair accepts omitted reasoning status on paired completed items while preserving strict message and terminal completion checks. Valid terminal usage is retained even if later local assembly fails; historical unknown counts are not retroactively filled.

These changes are evaluated together in v2. **This is not a controlled prompt-only A/B experiment:** the annotation version and transport behavior also changed, and each model request has one observed trial. The v1 table documents the decision process; it is not pooled with v2 or held-out measurements.

## Reproduce a saved report

From the repository root:

```bash
uv run grounding-eval report reports/2026-10-15/development-v1
```

The command validates saved cases, records, status and fingerprints before regenerating the summary. It makes no inference calls and never converts a run with errors into a complete-success run. For new inference, follow the root README and use a new output directory; model output and timing are not expected to be bit-for-bit repeatable.
