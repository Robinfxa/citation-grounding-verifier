# Independent annotation comparison — 12 dev pilot

This compares the original `v2-pilot-author-draft-1` with one independent LLM review. Both blind batches were locked before author gold was opened; their files remain unchanged. No human review, verifier execution, model API call, external lookup, or future-test access occurred.

- 123 claims: 122 labels agree; p04-c09 is author **S** versus locked independent **U**.
- Every original answer anchor is an exact substring with correct offsets. p04-c10 still excludes a material scope modifier despite having numerically correct offsets.
- All 128 author citation spans are exact source substrings. Exact matching does not establish sufficient proof or minimality.
- The 12 frozen passage collections match the authorized source manifest. The combined pilot equals the two original author batches.

| Priority | Claims | Finding and proposed action |
| --- | --- | --- |
| High | p04-c09 | The generic “unspecified settings” overlooks the adjacent flags-cleared exception. Narrow to unspecified **non-flag settings**; keep the original U in the locked review. |
| High | p04-c10 | The answer's “For conversion as well as later arithmetic” is absent from the candidate anchor. Delete that ambiguity, then split create_decimal precision and Decimal-constructor contrast into two S facts. |
| High | p07-c04 | The selected author quote gives a sufficient condition, while the claim states necessity. Keep S and replace it with the explicit “must be pub … private item … disallow” rule. |
| Medium | p10-c05/c06 | Keep RU=RC plus the SELECT rules, and add the Read Committed title to expose the necessary scope link. |
| Medium | p02-c04, p05-c08 | Each has a sufficient single-passage alternative. Remove mandatory cross-passage difficulty assertions or revise the claims before a new review. |
| Medium | p06-c07, p12-c08 | Split size/hash and functions/procedures under the same atomic-fact rule used for p04-c10. Each component remains S. |
| Medium | R09 (12 claims) | Complete quoted method/type/exception/coreference scope; detailed alternatives are in comparison.json. |
| Low | R10 (68 claims) | Trim unrelated branches, properties or examples when scoring evidence precision. Multiple sufficient evidence sets remain valid. |

The three atomic splits yield **126 claims**, with no loss of answer facts. Shared exact answer anchors and shared source evidence are valid. A before/after ordering, conditional transition or causal relation can remain one claim when that relation is the actual fact.

The necessary cross-passage claims independently retained are **p01-c03** and **p10-c05/c06**. Their evidence sets expose all required identity and inheritance/mapping links. p02-c04 and p05-c08 must not reject valid single-passage evidence merely because the author selected a longer proof.

`comparison.json` records all 123 original author labels, evidence sets, rationales and anchors beside the untouched independent judgments, with concrete passage offsets and manifest-derived source-line locators. Those raw-line locators are derived from the manifest; raw source files were not opened. The original Chinese review text is preserved as the actual review record.

`human-review-queue.json` and `human-review-queue.md` remain **pendinghuman**. These descriptive counts are not verifier accuracy, human validation, or reviewer consensus.

