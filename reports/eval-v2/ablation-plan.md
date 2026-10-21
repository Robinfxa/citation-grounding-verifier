# Development experiment: sufficient citations in Minimal

Status: prespecified, not yet measured. This plan uses development material only. The final test population has not influenced the candidate instruction or adoption rule.

## Hypothesis and one changed factor

The [development attribution](pilot-resume-20261020-dev-review.json) found citations that were literal substrings but omitted the API identity or governing mode/condition. Minimal already asks for exact citations and preserved qualifications. The candidate adds only this sentence to the end-to-end `MINIMAL` prompt, immediately before `Give brief reasoning.`:

> For supported/refuted claims, cite a minimal sufficient set that includes the entity or API identity and every governing condition; include the nearby antecedent when a short quote omits either.

No extraction instruction, oracle prompt, Optimized prompt, model, annotation, alias, scoring rule or transport behavior changes. The current version is the control. The candidate is evaluated from an isolated source copy; the normal application prompt is not adopted before results are examined. Source fingerprints and the exact one-file diff must be saved before inference.

## Population and measurements

Use all 12 reviewed development pilot cases, with dataset hash `701fe4bf85bb745824d460399b6dd6efd8302856e48cea4e751bb09f8ca040df`, Minimal end-to-end only. Preserve every outcome. Use Codex / `gpt-6.1-sol`, seed 20261015, provider timeout 120 seconds, operation timeout 240 seconds, zero transport retries, and at most six attempts per operation. The requested output-token limit is not an effective Codex limit. Other settings must equal the new complete development baseline; any mismatch invalidates the controlled comparison.

Two observations per condition are planned. Control observation 1 comes from the [explicitly mapped development population](completion-dev-20261020/combined-analysis/source-row-map.json), after confirming its fingerprints, settings and population match. This is a failure-inclusive analytical combination of immutable rows, not a successful single CLI run: 11 Minimal end-to-end outcomes are OK and the original p07 protocol error remains ERROR. Only previously unattempted jobs were recovered; their later block timing remains a limitation. Three new 12-case blocks run in the fixed order: candidate observation 1, control observation 2, candidate observation 2. This costs 36 expected calls before repairs, with a hard new ceiling of 216 provider attempts. Missing observations or errors are never silently replaced by a different control population. The user has authorized necessary calls; actual use, unknown costs and all earlier historical allocations remain separately recorded.

Each block uses a fresh output directory, frozen selection and durable start/exit receipt. Stop a block on a model error and preserve later NOT_RUN records; diagnose before deciding a separately recorded recovery. Never rerun an unknown outcome or choose a best repetition. The fixed block order does not eliminate temporal provider drift; report that limitation and the exact observed model identities.

## Decision rule

Compare failure-inclusive joint label and evidence scores, exact cases, returned citation sufficiency on the known condition/identity errors, input/output tokens and operation latency. Review all changed outcomes, including regressions and surface-match artifacts. A citation is not semantically sufficient merely because it contains a gold substring. No gold/alias editing is allowed in response to predictions.

Adopt only if the development evidence supports improved sufficient citations without a material label/extraction regression and the resource tradeoff is acceptable. Otherwise retain the original prompt and report a rejected or inconclusive optimization. Do not claim a statistically established improvement from this small paired experiment. Paired resampling must keep source families and repetitions together; repeats do not create new independent sources. Final test inference follows the recorded adoption decision and freeze.

This experiment changes prompt content only. Existing request/attempt/error logs and the accepted provider/runner boundary behavior are reused; no new logging path or telemetry is introduced. Independent review checks the one-factor diff, controls, saved-run replay and the inference limits actually enforced.
