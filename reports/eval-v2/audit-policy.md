# Frozen semantic audit policy (v1)

This audit supplements strict scoring; it never rewrites main scores, gold or aliases. Freeze this file's hash and the selected case IDs before final test inference. Select up to 24 test cases by source family and primary category, using only metadata. Include all three methods on the same cases in the first full run. Additional unmatched-output diagnostics are not population estimates.

## Stage 1: extraction and alignment

An independent reviewer receives only the answer, gold claim texts and anonymously shuffled prediction texts. Do not inspect the run, method key, source passages, gold verdicts, predicted verdicts, reasoning or citations at this stage. Classify all gold and predicted items exactly once:

- `equivalent`: one gold and one prediction assert the same independently checkable proposition, including entity, number/unit, time, modality, negation, attribution and conditions. Stylistic paraphrase is allowed. A proposition being true does not establish equivalence.
- `merged`: multiple independently checkable gold propositions appear in one prediction. No full atomic-claim credit, even if all verdicts would be identical.
- `split`: one gold proposition is divided over several predictions that individually lack its complete scope. No full credit. Independent repeated complete propositions are duplicates, not splits.
- `scope_changed`: one-to-one text resemblance with a materially different number, subject, quantifier, condition, version, modality or negation. No equivalence credit.
- `missing`: gold assertion omitted; `extra`: prediction has no equivalent gold assertion; `duplicate`: repeated prediction beyond a previously accounted complete proposition. For duplicates, name the earlier prediction index in the rationale.
- `uncertain`: relation cannot be decided from these texts. Preserve it with a reason; no automatic credit. An apparent missing gold fact is flagged for errata review without changing the frozen answer key.

Relations must partition both inventories without reusing an item. A single group can contain several items only for merged, split or uncertain relations. Meaningful split/merge counts are audit findings, not inferred from strict unmatched counts. The reviewer records actual identity/type, model when known, completion time and exposure. Programmatic validation and a hash lock precede stage 2. Identical text may be mechanically identified, but substantive review is not claimed merely because a checker runs.

## Stage 2: label and evidence

After the stage-one lock, expose context passages, gold verdicts and predicted verdicts/reasoning/citations, while method names remain hidden. For each equivalent pair, independently assess:

1. **Label:** correct, incorrect or uncertain under the frozen context-only S/C/U policy. Missing information alone is not contradiction. Equal-scope unresolved conflict is U. Do not use external knowledge.
2. **Evidence sufficiency:** sufficient, insufficient or uncertain for S/C; not applicable for U. Exact quotation existence is necessary but not sufficient. Include every needed antecedent, qualifier and multi-passage link. Alternative sufficient quotes can pass even when the strict gold-span proxy fails.
3. **Quote economy:** compact, redundant or not applicable. Extra irrelevant/redundant text does not erase an otherwise sufficient set, but is separately counted. A very long quote is not automatically sufficient.

Any gold-label dispute is recorded as uncertain with an erratum candidate; no post-test answer-key repair is credited in the current score. U requires no citations. Failed requests remain in gold and requested-case denominators; an operational error is not a U judgment. Audit discussion must distinguish scorer undercount from actual model failure.

## Summary and limits

Semantic decomposition uses only one-to-one equivalent pairs. Semantic joint-label credit additionally requires a correct label; joint-evidence credit also requires sufficient evidence (or a correctly labeled citation-free U). All gold and predictions remain in F1 denominators. Uncertain, merged and scope-changed items receive no automatic correctness credit, with counts shown separately. Report numerator/denominator, cases, source families, method, review exposure and unresolved items. The audit subset is not the full test population, and a style-recognizable method may weaken blinding.

AI non-author review, deterministic validation and Robin's eventual human review are distinct evidence. Human review and interview proficiency remain pending until Robin performs them. Reviewer disagreement and original judgments are retained; no vote is fabricated from a single reviewer.
