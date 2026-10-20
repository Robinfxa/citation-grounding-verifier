# Independent AI annotation evidence for the 60 new cases

These are actual completed reviews of the licensed-documentation cohorts,
not new reviews or verifier predictions. The three original blind judgment
files contain 145 dev, 275 first-batch test and 245 second-batch test judgments
(665 total). The accepted author gold contains 132 + 210 + 200 = 542 claims;
different coherent atomicity does not by itself imply missing assertions.
Reviewers independently extracted and locked their judgments before opening
author gold. The preserved affected reviews then checked the real revisions.
Human review and measured model difficulty are not claimed.

`publication-manifest.json` binds the accepted main candidate and metadata
without changing their hashes. Every published source entry records both
`original_sha256` and `published_sha256`, plus its precise rule:

- `*.original.*` is a byte-identical copy of the original judgment, comparison
  or affected-review record after checking for private paths and unrelated
  corpus material. Its two hashes intentionally match. Historical private-file
  names or `private_test_content` flags describe the original work stage.
- `*.projected.*` is a separate safe projection. Lock projections omit only
  the listed private input-path/sharing-route fields. Decision projections
  retain actual issue decisions and atomicity rules, while omitting private
  routing, snapshot paths and repeated gold payloads. If no field is omitted
  and serialization matches, a projection can also be byte-identical; each
  entry's flag and two hashes state the fact. A changed projection hash must
  never be presented as the original lock hash.
- `*-author-to-accepted.diff.json` is an author-computed field-level difference
  map between the archived original component and the accepted component.
  It identifies additions/removals, unchanged claim IDs and the six controlled
  punctuation-only input repairs. It is not an independent review itself.

The first-batch `revised-1` affected review contains its genuine intermediate
residual requests; the `revised-2` acceptance resolves them. Dev DR01 is also
separate from the first affected acceptance. These stages are retained rather
than rewriting earlier review history into a clean final record.

`input-reconstruction.json` identifies the original public author components,
their hashes and a deterministic reconstruction of the original context +
answer + origin blind input. The original blind input is distinct from the
accepted candidate when explicit punctuation-only revisions occurred. No
unchanged gold is silently counted as newly independently reannotated: it is
reused only after the recorded exact-field checks.

The original pilot uses the existing public review under
`reports/eval-v2/annotation-review/`; this archive covers only the added sixty.
All quoted source material here belongs to the licensed documentation main
candidate, with the upstream notices in the parent directory. No private
news text, third-party natural response or its independent annotation is
included in this review archive.
