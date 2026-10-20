# RAGTruth natural-response auxiliary

This separate selection contains twelve actual complete RAGTruth Summary
responses with their original source IDs, models, train split, good quality,
temperature, original span types/offsets and hashes. It is not part of the
72-case documentation main candidate. Six selected responses have upstream
error spans and six do not. Spans are not treated as complete claim gold.

The fixed upstream repository revision is
`c103204b9ce28d6bbad859304bf30de72b8ed8fe`. `RAGTruth-LICENSE` preserves its
MIT notice. That notice is not asserted to grant complete redistribution
rights in underlying news, MARCO or Yelp material. Full source/response data
and reconstructed scoring files stay in the private acquisition workspace.
Public files contain IDs, hashes, source-relative Unicode intervals and newly
AI-authored annotations. Short factual wording in those annotations can
coincide with upstream text; no full news text, full response, or direct
quote/anchor substring fields are bundled here.

Reproduction has two distinct steps. The first reconstructs the unchanged raw
records without a question prefix or claim gold:

```sh
python datasets/v2/realistic-draft/auxiliary/rebuild_ragtruth.py --output PRIVATE_DIRECTORY
```

The second reconstructs the adapted inputs and complete claim annotations from
the recipe's offsets and hashes. The original Summary instruction becomes
`Question: {original prompt first line}\n\nAnswer: {complete original response}`.
The original response and source bytes after UTF-8 decoding remain unchanged;
upstream span offsets remain relative to the original response, while gold
anchors add the exact prefix length. The instruction is never evidence.

```sh
python datasets/v2/realistic-draft/auxiliary/rebuild_ragtruth_scoring.py --recipe datasets/v2/realistic-draft/auxiliary/ragtruth-claim-recipe.reviewed-1.json --raw-input PRIVATE_DIRECTORY/ragtruth-natural-selected.private.jsonl --output PRIVATE_SCORING_DIRECTORY
```

Use **`PRIVATE_SCORING_DIRECTORY/scoring-cases.jsonl`** and its adjacent
`scoring-cases.manifest.json` for auxiliary measurement: nine complete natural
responses, 125 reviewed claims (111 supported, 12 unsupported, 2 contradicted).
`scoring-blind.jsonl` and `scoring-sealed-gold.jsonl` are exact row selections
from the twelve-record files. No original response was edited.

The full `private-cases.jsonl`, `blind.jsonl` and `sealed-gold.jsonl` retain all
twelve original records and 170 annotations for diagnosis and reconstruction.
**Do not score all twelve as a uniquely labelled population.** Records 2660,
4100 and 5639 have genuinely non-unique year, causal or actor/modifier
attachment. Whole cases are excluded; ambiguous gold is not silently removed
while retaining the complete answer in the score. Ordered IDs, exclusion
categories and the pre-verifier-results decision rule are public in
`ragtruth-scoring-membership.reviewed-1.json`. This purposive nine-case
auxiliary subset does not represent all RAGTruth or replace the main set.
Auxiliary rows retain `split=dev` and `category=synthesis` as Summary-task
metadata; they are a separate population and are not added to the main set's
split or case-category counts. Two scoring answers have only supported facts;
the other seven contain reviewed unsupported or contradicted assertions.

The fixed twelve were independently decomposed into 197 claims and locked
before the reviewer opened the author's 161-claim draft. A concentrated
revision produced 170 diagnostic annotations: the same reviewer accepted all
67 changed/added and 103 exact unchanged claims, and accepted the nine-case
membership. `ragtruth-review-status.reviewed-1.json` records original evidence
hashes, the thirteen decision categories and the metadata projection rule.
Original blind judgments and full-text review artifacts remain private.
The preserved `author-draft-1` recipe and packet lock retain their historical
pending status; the new reviewed recipe binds the subsequent acceptance.

Reconstruction verifies the raw-acquisition hash, all sliced strings, all
seven full/subset output hashes, membership, and the repository notice before
writing outputs. It emits two strict adjacent manifests, exact decoded-field
source files and the repository MIT notice for local consumer loading. These
checks establish byte-level reproduction, not underlying news redistribution
rights. Review was by independent AI, not a human. The scripts do not perform
inference or claim any verifier measurement results.
