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

## Development v2 and final freeze

[Development v2](development-v2/summary.json) used the corrected 18-claim development set and implementation `48de5a5`. All **48/48 jobs succeeded** with no retry, repair, quota stop, cleanup failure or source change. Usage was complete for every request.

| End-to-end, eight development cases | Joint label F1 | Gold evidence coverage | Exact cases | Median / p95 ms | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heuristic | 0.6061 | 0.3636 | 3/8 | 0.614 / 0.912 | 0 / 0 |
| Minimal LLM | 0.9143 | 0.9091 | 6/8 | 4,444 / 7,910 | 2,978 / 1,147 |
| Optimized LLM | 1.0000 | 1.0000 | 8/8 | 7,514 / 9,563 | 8,785 / 1,681 |

Evidence coverage in both development tables uses the **11 non-UNSUPPORTED gold claims** as its denominator; the annotation correction added only an unsupported development claim. It does not use all 17 or 18 claims as that denominator.

Both LLM oracle tracks classified all 18 claims correctly with complete gold evidence. The optimized Kelm quotation now includes its entity antecedent, and the corrected Diska inventory matches the extracted facts. These observations support retaining the revision, not a general claim of perfect performance. The paired development **end-to-end** joint-label F1 difference is +0.0857, with a 95% family-bootstrap interval of [0.0000, 0.2195]. Eight development cases and a single model trial are insufficient to establish a reliable improvement.

[The final freeze](freeze.json), committed in `133c1b1`, records the exact code, prompt and dataset hashes, the successful 410-test integration checkpoint, and the fact that no held-out predictions or scores had been inspected. The 24 held-out cases / 50 claims used these unchanged versions. Held-out outputs are for reporting and failure analysis; no aliases, prompts or scoring rules were changed in response to them.

## Held-out results

[Held-out summary](held-out/summary.json), [configuration](held-out/config.json), [request records](held-out/records.jsonl), [selected cases](held-out/cases.jsonl), [completion receipt](held-out/completion.json).

All **144/144 jobs succeeded**. Code, prompts and dataset match the pre-test freeze. There were 120 provider calls across both LLMs and both tracks, no retry/repair, no quota stop or cleanup failure, and complete token accounting. The two tracks are separate experiments; do not combine their scores or report oracle calls as end-to-end cost.

| Approach / track | Joint label F1 | Macro F1 | Joint evidence F1 | Decomposition F1 | Evidence coverage | Exact cases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Heuristic / end-to-end | 0.3299 | 0.2162 | 0.3299 | 0.9485 | 2/35 | 6/24 |
| Minimal / end-to-end | 0.9800 | 0.9778 | 0.9600 | 1.0000 | 34/35 | 22/24 |
| Optimized / end-to-end | 0.9600 | 0.9667 | 0.9600 | 0.9600 | 33/35 | 23/24 |
| Heuristic / oracle | 0.3400 | 0.2193 | 0.3400 | 1.0000 | 2/35 | 6/24 |
| Minimal / oracle | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 35/35 | 24/24 |
| Optimized / oracle | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 35/35 | 24/24 |

Oracle label accuracy is 17/50, 50/50 and 50/50 respectively. End-to-end predicted-claim counts are 47, 50 and 50; correctly aligned-and-labeled counts are 16, 49 and 48. Evidence coverage's denominator is the **35 non-UNSUPPORTED gold claims**, and unmatched predictions cannot receive gold evidence credit. Literal citation validity is 3/3, 48/48 and 46/46 in the end-to-end tracks. This perfect structural property coexists with semantic and alignment failures.

| Approach / track | Median / p95 ms | Provider calls | Input / output tokens | Cached input | Unknown-usage requests |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heuristic / end-to-end | 0.604 / 1.248 | 0 | 0 / 0 | 0 | 0 |
| Minimal / end-to-end | 4,497 / 8,271 | 24 | 8,972 / 3,614 | 0 | 0 |
| Optimized / end-to-end | 7,822 / 10,022 | 48 | 26,293 / 5,198 | 0 | 0 |
| Heuristic / oracle | 0.523 / 2.277 | 0 | 0 / 0 | 0 | 0 |
| Minimal / oracle | 4,118 / 5,699 | 24 | 9,676 / 3,053 | 0 | 0 |
| Optimized / oracle | 4,670 / 5,977 | 24 | 17,572 / 3,362 | 0 | 0 |

Dollar cost remains `null` for the subscription route, not zero. The heuristic has no provider charge, excluding local compute. The 60-second operation and 30-second provider deadlines did not trigger in this run. Successful measurement of this account and model does not establish other accounts' capability, subscription allowance or latency.

The 95% end-to-end joint-label F1 intervals are heuristic **[0.1633, 0.5054]**, minimal **[0.9375, 1.0000]**, optimized **[0.8750, 1.0000]**. The paired optimized-minus-minimal differences are:

| Metric | Observed difference | 95% paired interval |
| --- | ---: | ---: |
| Joint label F1 | −0.0200 | [−0.1200, +0.0577] |
| Joint evidence F1 | 0.0000 | [−0.1042, +0.0833] |
| Exact-case fraction | +0.0417 | [−0.0833, +0.1667] |

None establishes a reliable optimized advantage. The perfect oracle results generate degenerate intervals; that does not mean zero uncertainty. Macro-F1 bootstrap intervals have two undefined draws out of 10,000, retained in the JSON. Primary joint-label/evidence and exact-case intervals have no undefined draws.

For the six cases in each category, end-to-end joint-label F1 is:

| Category | Heuristic | Minimal | Optimized |
| --- | ---: | ---: | ---: |
| Supported | 0.1739 | 1.0000 | 0.8333 |
| Subtle distortion | 0.0000 | 1.0000 | 1.0000 |
| Extrinsic | 0.9231 | 0.9286 | 1.0000 |
| Multi-passage synthesis | 0.1667 | 1.0000 | 1.0000 |

### Failure analysis without rescoring

Only three LLM end-to-end reports fail the frozen exact-case metric. A separate agent reviewed these cases after the freeze and run, without changing annotations or scores:

- **Minimal / `ceruni-ledger`:** the model calls an unrecorded replication state CONTRADICTED for a claim that it is disabled. Unrecorded does not prove disabled or its negation; UNSUPPORTED is required. This is a genuine label error despite a verbatim quotation.
- **Minimal / `tevrin-access`:** both contradiction labels and the substantive role-permission counterevidence are correct. The first quote starts at “editors may rename” and omits “In Tevrin Access,”, so it fails containment of the complete frozen gold span. This is a conservative evidence-proxy loss; it is not presented as a false label.
- **Optimized / `nuvali-reader`:** “accepts amber formats” and “accepts violet formats” are unregistered plural rewrites of singular format claims. Both become missing gold claims plus extra predictions, even though the returned quotations contain the source's full acceptance sentence. The wording also admits a broader format-range reading; the independent reviewer did not certify it as necessarily equivalent. No semantic-adjusted score or new aliases are introduced.

The heuristic returns unsupported for all 15 gold contradictions. `ivaro-frame` explicitly rejects exactly 12 cells and sets a minimum of 3, but both invalid-size claims become unsupported; `falune-pool` supplies named counterexamples, yet the universal claims also become unsupported. High lexical extraction coverage therefore does not imply useful semantic verification.

The measured minimal pipeline has the higher strict claim score and lower latency; optimized has one more exact case, with uncertainty spanning either ordering. Two-stage extraction gives explicit claim identity and a place for repair, but this small experiment does not establish a quality benefit sufficient to justify its extra calls. Future work should compare a stronger inexpensive baseline, use independently human-reviewed natural answers, measure repeated model trials, and evaluate semantic alignment on a new holdout. None of those unperformed experiments is represented as a result here.

## Reproduce a saved report

From the repository root:

```bash
uv run grounding-eval report reports/2026-10-15/development-v1
uv run grounding-eval report reports/2026-10-15/development-v2
uv run grounding-eval report reports/2026-10-15/held-out
```

The command validates saved cases, records, status and fingerprints before regenerating the summary. It makes no inference calls and never converts a run with errors into a complete-success run. For new inference, follow the root README and use a new output directory; model output and timing are not expected to be bit-for-bit repeatable.
