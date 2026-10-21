# RAGTruth natural-response auxiliary evaluation

This is a separate, purposive sample of nine pre-existing model-generated Summary responses from RAGTruth. The source responses were not synthesized or mutated for this evaluation. They differ from the main benchmark’s generated/controlled answers on real technical documents. They are not human-authored answers or a representative reproduction of the full RAGTruth benchmark. The scoring input uses the documented question/answer wrapper; upstream answer text remains unchanged, and questions are not evidence.

Twelve responses remain in the diagnostic provenance population. Before any system predictions, three whole cases with non-unique readings were excluded from scoring; the frozen scoring population is nine cases, 125 gold claims and nine source families: 111 SUPPORTED, 2 CONTRADICTED and 12 UNSUPPORTED. Membership, exclusions, gold/aliases, source, methods, settings and the separate 90-attempt cap were frozen before inference. No failed or difficult prediction was removed afterward.

The same Codex/gpt-6.1-sol source checkpoint and settings of 120 seconds per provider call and 240 seconds per operation as the main benchmark were used. All errors and unattempted cases retain their original denominators. No semantic audit of these natural-response predictions is claimed; strict end-to-end matching remains sensitive to paraphrase and atomic granularity. Low strict F1 cannot establish harder factual classification, and strong oracle scores on nine mostly-supported cases cannot establish general performance on RAGTruth.

## Publication and reproducibility boundary

Original news/response text, complete gold, predictions, quotations, reasoning, raw run/config/logs and actual absolute launch arguments remain private. Public artifacts contain only fixed identifiers/hashes, pre-result exclusions and recipes, aggregate quality/confusion/coverage/resources and safe receipts. Repository MIT does not clear third-party news redistribution. No per-case natural-response excerpts or failure examples are published.

The [input reconstruction recipe](../../../datasets/v2/realistic-draft/auxiliary/README.md) can reconstruct the selected inputs from legally acquired upstream material. It cannot recreate stochastic model outputs. Exact numerical replay requires a holder’s original private saved run. The public aggregate alone is not a substitute for those raw artifacts. Human review remains pending.

## Actual completion and oracle results

The single original CLI exited 0: 54/54 OK, zero ERROR and zero NOT_RUN, with 36 model operations and 46/90 provider calls. One output repair is included; transport retries are zero. The remaining 44 attempts were unused. CLI wall time was 1377.733 seconds. Source/input/settings/cleanup checks passed; no job was rerun or replaced.

Oracle supplies all 125 frozen gold claims directly. It separates classification from extraction. Evidence F1 below is correct-label plus literal coverage of a frozen gold-quote set, a conservative span proxy.

| Method | Correct labels | Macro F1 | Non-S coverage | False support | Evidence F1, span proxy | Exact cases |
|---|---:|---:|---:|---:|---:|---:|
| Heuristic | 12/125 | 0.058394 | 14/14 | 0/14 | 0.096000 | 0/9 |
| Minimal | 123/125 | 0.861740 | 14/14 | 0/14 | 0.440000 | 0/9 |
| Optimized | 122/125 | 0.848822 | 14/14 | 0/14 | 0.696000 | 1/9 |

| Method | Gold class | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| Heuristic | SUPPORTED | 0/0 = null | 0/111 = 0.000000 | 0.000000 |
| Heuristic | CONTRADICTED | 0/0 = null | 0/2 = 0.000000 | 0.000000 |
| Heuristic | UNSUPPORTED | 12/125 = 0.096000 | 12/12 = 1.000000 | 0.175182 |
| Minimal | SUPPORTED | 110/110 = 1.000000 | 110/111 = 0.990991 | 0.995475 |
| Minimal | CONTRADICTED | 1/1 = 1.000000 | 1/2 = 0.500000 | 0.666667 |
| Minimal | UNSUPPORTED | 12/14 = 0.857143 | 12/12 = 1.000000 | 0.923077 |
| Optimized | SUPPORTED | 109/109 = 1.000000 | 109/111 = 0.981982 | 0.990909 |
| Optimized | CONTRADICTED | 1/1 = 1.000000 | 1/2 = 0.500000 | 0.666667 |
| Optimized | UNSUPPORTED | 12/15 = 0.800000 | 12/12 = 1.000000 | 0.888889 |

Both model methods recall only 1/2 C claims. Zero oracle false support is observed over 14 non-S claims with full coverage; this small sample does not establish a general low-error guarantee. Heuristic predicts U throughout oracle: 12/125 labels are correct, so its zero false support is not reliable verification. All aggregate confusion matrices and numerator/denominator values remain public in [aggregate-results.json](aggregate-results.json).

## Strict end-to-end results

| Method | Gold / predictions | Strict matches | Omitted / extra | Joint-label F1 | Joint-evidence F1 | Non-S coverage |
|---|---|---:|---|---:|---:|---:|
| Heuristic | 125 / 87 | 0 | 125 / 87 | 0.000000 | 0.000000 | 0/14 |
| Minimal | 125 / 143 | 8 | 117 / 135 | 0.059701 | 0.037313 | 1/14 |
| Optimized | 125 / 182 | 2 | 123 / 180 | 0.013029 | 0.000000 | 0/14 |

Both model methods have 0/14 strict false support, but non-S identity coverage is only 1/14 and 0/14. Their 8/2 matched claims have correct labels; correctness of unmatched text is not established. Zero Optimized joint-evidence credit applies to its two strictly matched claims under the gold-span proxy, not a semantic finding about all 182 predictions. No per-case natural-response review or excerpts are published.

Literal citation validity is 133/133 and 120/120 for model oracle, and 138/138 and 170/170 for model end-to-end; literal validity does not prove sufficiency. End-to-end exact cases are 0/9 for both methods.

## Source-family paired sensitivity

Optimized minus Minimal; 9 source-family clusters, 10,000 percentile resamples, seed 20261015, 95% intervals. These characterize this sample, not annotation bias, all model randomness or representative RAGTruth performance.

| Track | Metric | Difference | 95% interval | Defined / undefined draws |
|---|---|---:|---|---|
| oracle | joint_label_f1 | -0.008000 | [-0.022727, 0.000000] | 10000 / 0 |
| oracle | joint_evidence_f1 | +0.256000 | [0.203390, 0.304688] | 10000 / 0 |
| oracle | macro_f1 | -0.012918 | [-0.026873, 0.000000] | 8995 / 1005 |
| end-to-end | joint_label_f1 | -0.046672 | [-0.094263, -0.003947] | 10000 / 0 |
| end-to-end | joint_evidence_f1 | -0.037313 | [-0.066914, -0.008621] | 10000 / 0 |
| end-to-end | macro_f1 | -0.042258 | [-0.108802, -0.003923] | 8994 / 1006 |

Oracle shows higher Optimized evidence-span coverage, with no label gain. Strict end-to-end differences favor Minimal under this frozen metric and this nine-case sample; only 8/2 identities match and no semantic audit was performed, so this does not establish general faithfulness superiority. Undefined macro-F1 draws remain counted; exact-case degeneracy is not zero uncertainty.

## Measured resources

| Method / track | Calls | Input / output tokens | Repair / retry | Operation sum s | Median s | p95 s |
|---|---:|---|---|---:|---:|---:|
| heuristic/oracle | 0 | 0 / 0 | 0 / 0 | 0.302 | 0.024 | 0.079 |
| heuristic/end-to-end | 0 | 0 / 0 | 0 / 0 | 0.219 | 0.022 | 0.042 |
| minimal/oracle | 9 | 13448 / 9630 | 0 / 0 | 215.405 | 25.192 | 31.797 |
| minimal/end-to-end | 9 | 12495 / 14562 | 0 / 0 | 308.812 | 38.750 | 47.083 |
| optimized/oracle | 9 | 16409 / 12634 | 0 / 0 | 273.262 | 32.254 | 37.527 |
| optimized/end-to-end | 19 | 23791 / 26152 | 1 / 0 | 562.334 | 62.232 | 90.908 |

Usage is complete for all 46 calls: 66143 input, 62978 output and 0 cached input tokens. Returned models are gpt-6.1-sol. Subscription usage is not dollar cost; whole dollars remain unknown. Operation-time sum is 1360.333 seconds, distinct from CLI wall time.

Optimized/end-to-end median operation time is 62.232 seconds under the 240-second operation limit. The service default is 60 seconds; these measured successes do not establish default-timeout success. No counterfactual calls/rescoring were added. Requested `max_output_tokens=8192` is not applied on the Codex route; effective cap is null.

The [execution receipt](execution-receipt.json) binds the 18 private original files by hash. The [plan](experiment-plan.json) and [portable live-run example](commands.json) preserve pre-call controls and input identities. Preparation status and inherited data-author limitations describe the pre-run handoff; execution-receipt.json is the current measured status.

## Actual offline replay

The private saved report was regenerated and the public aggregate projection compared byte-for-byte using the public consumer. Its actual exit code was 0 in 8.064 seconds; all 18 private original files remained identical. Network, inference, environment-file, settings and credential loading were guarded. The [actual replay receipt](offline-replay-verification.json) records the script, source and aggregate hashes; zero new provider calls were made.

With dependencies installed, export the pinned runtime and use the original private saved run held locally:

```sh
ragtruth_checkpoint_dir=$(mktemp -d)
git archive 324559dccba4624dfa803849f5fd26284c7b27f4 src | tar -x -C "$ragtruth_checkpoint_dir"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ragtruth_checkpoint_dir/src" .venv/bin/python reports/eval-v2/ragtruth-20261020/replay-aggregate.py --private-run "$ragtruth_private_run"
```

Set `ragtruth_private_run` to the holder’s original saved-run directory. Acquisition recipes rebuild inputs, not these stochastic predictions. A new live reproduction consumes calls and needs a fresh private output path; it cannot overwrite the saved evidence. The [publication policy](publication-policy.json) remains binding.
