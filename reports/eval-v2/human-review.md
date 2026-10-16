# Human review and interview checklist

**Status: pending human review.** AI authorship, non-author AI review and program checks have occurred; Robin has not been recorded as reviewing these annotations or completing the exercises. This checklist does not add an approval gate to ordinary implementation work.

Use the [revised pilot](../../datasets/v2/pilot.jsonl), [original draft](../../datasets/v2/pilot-author-draft-1.jsonl), [source mappings](../../datasets/v2/pilot.manifest.json) and [full disagreement records](annotation-review/comparison.json). Claim IDs below refer to the original draft; the revision metadata maps split claims to their new IDs.

| Check | Original claim(s) | What Robin should verify |
| --- | --- | --- |
| Missing evidence versus contradiction | p04-c09; p06-c09/c10 | Explain why an unqualified default-settings claim needs the flags exception, and why hash verification or a 15-minute cache cannot be inferred from a documented field/API. Identify what would constitute direct counterevidence. |
| Answer scope | p04-c10 | Find “later arithmetic” in the original answer and explain why an exact substring anchor still omitted a material assertion. Check the revised conversion-only wording. |
| Necessary versus sufficient condition | p07-c04 | Read the old and revised Rust quotations. Explain why “A implies B” alone does not justify “B requires A.” |
| Genuine multi-passage link | p01-c03 | Trace the named tar filter through every inherited restriction. Remove one necessary identity link mentally and explain what is lost. |
| Mode mapping and scope | p10-c05/c06 | Trace Read Uncommitted → Read Committed → the SELECT rule, including the heading that assigns the rule to the correct mode. |
| Numeric and version scope | p04-c04–c07; p03-c05 | Separate precision nine from rounding mode, and preserve the Python 3.13 / non-strict qualifier when judging the symlink-loop claim. |
| Atomicity | p06-c07; p12-c08 | Check the separate size/hash and function/procedure assertions, including the before/after ID mapping and shared answer anchors. |
| Evidence economy and difficulty | p02-c04; p05-c08 | Find sufficient single-passage evidence. Explain why these no longer count as necessarily cross-passage, and why a valid shorter quote should not be penalized for missing irrelevant prose. |

The [original AI review queue](annotation-review/human-review-queue.json) retains all issues and priorities. A later human record should include reviewer identity, time, case/claim IDs, decision, source-based reason and unresolved questions. Do not change its human status merely because an AI revision passed.

## Explain and operate the project

- [ ] Follow one request through the [code walkthrough](../../docs/code-walkthrough.zh-CN.md) using the actual symbols.
- [ ] Answer the [16 interview questions](../../docs/interview-self-check.zh-CN.md) without reading the prepared answer first.
- [ ] Complete the three exercises in a disposable copy: irrelevant but legal quotation, a scoring regression that genuinely fails, and a C/U boundary with the evidence needed to settle it.
- [ ] Distinguish historical v1 measurements, v2 offline acceptance and experiments that have not run. No controlled v2 optimization outcome can be explained as a measured result yet.
- [ ] Reproduce a saved report without inference, then explain why changing its scorer should reject replay.

No boxes are pre-checked. Producing learning material is not evidence of interview readiness.
