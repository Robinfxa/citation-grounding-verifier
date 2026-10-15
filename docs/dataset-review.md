# Dataset review and freeze

The 32 main cases and six diagnostic cases received a separate, non-author agent review before any system predictions were inspected. This is agent-assisted annotation review, not human annotation or an inter-annotator agreement study.

The reviewer read every answer, passage, claim, label, rationale, alias and evidence alternative. It independently checked bounds and verbatim quotations using standard-library code rather than relying on the product's validator. It also checked split/family isolation, normalized alias collisions, multi-passage evidence completeness, and the distinction between missing evidence and explicit contradiction.

## Findings resolved before freeze

| Case | Finding | Resolution |
| --- | --- | --- |
| `ivaro-frame` | The original “fewer than 12” acceptance statement could include sizes below the separately stated minimum of 3. | State the complete interval: at least 3 and fewer than 12. The two boundary contradictions remain explicit. |
| `diska-table` | A supported completion time and an unestablished caching explanation were combined into one unsupported gold item. | Add the supported timing fact separately; preserve the causal relation as unsupported. |
| `virel-scan` | A supported scan time and an unestablished causal explanation had the same coverage problem. | Add the supported timing fact separately; preserve the causal relation as unsupported. |

The revised causal aliases were reviewed before predictions, including confirmation that they cannot also match the timing-only claims. A focused second review passed all three changes. Reverse reconstruction reproduced the original complete-file hash, confirming that the other 29 main cases were unchanged. The diagnostic file hash was unchanged.

## Frozen version

| File | SHA-256 |
| --- | --- |
| `datasets/main.jsonl` | `90d760c1fb9cd4497e32466084db56e0534485a74a72acae08d758217a68477c` |
| `datasets/diagnostic.jsonl` | `39d581b9abfe695c263130b4e84439aa86aef66900186158b26716a265a34fb0` |

The original reviewed main-file hash was `c5391e0b8e10da9f4c29a751348ae940cb6b58013c008c68e64237605567365e`. Both review passes were completed on 2026-10-15. The accepted version has 66 claims: 17 development claims (8 supported, 3 contradicted, 6 unsupported) and 49 test claims (20 supported, 15 contradicted, 14 unsupported). Four case categories remain balanced, with two development and six test cases per category.

No aliases or labels may be added in response to held-out predictions. Later annotation changes require a new hash and review of the affected cases; they cannot silently replace this benchmark version.

## Limits

One independent agent review does not eliminate annotation bias. These fictional English systems are controlled examples rather than a natural distribution. Distinct family identifiers prevent shared entity facts across partitions; they do not prove that all reasoning patterns are statistically independent. Some evidence fragments rely on pronouns or context in their original passage. Exact gold-span coverage and frozen text matching remain conservative diagnostics, and can undercount other valid evidence or paraphrases. These limits apply even when structural validation passes.
