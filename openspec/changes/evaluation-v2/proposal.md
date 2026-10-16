## Why

The published benchmark contains short fictional answers and cannot establish performance on dense, realistic evidence. Its deterministic text alignment can also confuse valid paraphrases with extraction failures. A second evaluation must improve the measurement before claiming model improvements.

## What Changes

- Preserve v1 data and reports; replay them from the fixed original source and lockfile in an isolated directory.
- Make a versioned real-source dataset the default, with source-family splits, explicit provenance, licenses, answer anchors and non-author annotation review.
- Retain strict scoring, add transparent false-support and extraction diagnostics, and separately report a preselected, blinded semantic audit.
- Bound real calls explicitly, preserve complete requested populations, and support frozen subsets and repeated paired measurements.
- Perform a development-only controlled ablation before freezing the final comparison. Document failures, uncertainty, resource use and limitations.
- Provide a source-level walkthrough and interview exercises; identify human review as pending until it happens.

## Capabilities

### New Capabilities

- `evaluation-v2`: Real-source dataset validation, versioned measurement, bounded experiments and separate semantic auditing. This extends the unarchived `citation-grounding` evaluation contract; there are no archived main specs to modify.

### Modified Capabilities

None. The HTTP verification input/output, authentication and provider transport are unchanged.

## Impact

Changes are limited to evaluator/data assets, targeted evaluator tests, an evidence-driven prompt experiment if justified, and documentation. Existing service constraints and quote validation remain authoritative. No new runtime framework, retrieval system, automatic model judge or external publication is required.
