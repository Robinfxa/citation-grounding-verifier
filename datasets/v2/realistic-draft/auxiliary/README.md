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

The second reconstructs the actual scoring input and complete claim gold from
the recipe's offsets and hashes. The original Summary instruction becomes
`Question: {original prompt first line}\n\nAnswer: {complete original response}`.
The original response and source bytes after UTF-8 decoding remain unchanged;
upstream span offsets remain relative to the original response, while gold
anchors add the exact prefix length. The instruction is never evidence.

```sh
python datasets/v2/realistic-draft/auxiliary/rebuild_ragtruth_scoring.py --recipe datasets/v2/realistic-draft/auxiliary/ragtruth-claim-recipe.author-draft-1.json --raw-input PRIVATE_DIRECTORY/ragtruth-natural-selected.private.jsonl --output PRIVATE_SCORING_DIRECTORY
```

The second step verifies the fixed raw-acquisition hash, all sliced strings,
and byte hashes for `blind.jsonl`, `sealed-gold.jsonl` and `private-cases.jsonl`.
It also emits a strict adjacent manifest, exact decoded-field source files and
the repository MIT notice for local consumer loading. This mechanical result
does not establish semantic correctness or upstream redistribution rights.
The `author-draft-1` recipe is explicitly pending independent blind review;
use a later reviewed recipe when supplied. Independent reviewers must lock
their own extraction and labels before reading the recipe or sealed gold.
Human review and live verifier measurement are not claimed by these scripts.
