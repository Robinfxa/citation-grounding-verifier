## Purpose

Provide an auditable context-only factual verification report whose quotations are validated independently of model-generated judgments and whose failures remain distinguishable from missing evidence.

## ADDED Requirements

### Requirement: Context-only atomic judgments
The service SHALL expose POST /verify with context_passages and generated_answer, and return claims containing claim_text, verdict, reasoning and citations. Factual content SHALL be decomposed into independently assessable claims while retaining numbers, conditions, attribution, modality and causal qualifications. SUPPORTED SHALL mean fully entailed by the provided evidence; CONTRADICTED SHALL mean directly refuted; UNSUPPORTED SHALL mean not verifiable from the provided context alone. Unresolved mutually conflicting passages SHALL yield UNSUPPORTED with a brief conflict explanation. External knowledge SHALL NOT supply missing evidence.

#### Scenario: Mixed WAL answer
- **WHEN** an answer combines network-filesystem WAL support, two auxiliary files, a 1000-page checkpoint and default encryption, with the assignment's supplied passages
- **THEN** the target report contains separate CONTRADICTED, SUPPORTED, SUPPORTED and UNSUPPORTED claims with appropriate evidence

#### Scenario: Missing and conflicting evidence
- **WHEN** context says only that version 3 supports snapshots, or two equally scoped passages disagree about the snapshot default
- **THEN** a claim about the unspecified or conflicting default is UNSUPPORTED rather than inferred from external knowledge or arbitrary passage order

### Requirement: Exact evidence integrity
Every SUPPORTED or CONTRADICTED claim MUST have at least one citation. Every UNSUPPORTED claim MUST have no citations. Each citation index MUST be an integer, not a boolean, in the bounds of context_passages; each quote MUST be nonblank and an exact case-sensitive substring of that indexed passage. The system MUST enforce these invariants in code before returning a successful report, without whitespace, Unicode, punctuation or fuzzy normalization. Several citations MAY jointly establish one claim; citation existence alone SHALL NOT be presented as a proof of semantic correctness.

#### Scenario: Fabricated or misplaced quote
- **WHEN** a model cites index -1, true, an out-of-bounds passage, an empty quote, or a quote differing by a character from the indexed source
- **THEN** that output cannot be returned as a successful verification report

#### Scenario: Joint evidence
- **WHEN** a claim requires a fact from passage 0 and a linking fact from passage 1
- **THEN** both exact quotations can appear under one supported claim without requiring either quote alone to entail it

### Requirement: Explicit empty and failure behavior
The system SHALL return an empty claims list for blank answers or successfully identified answers with no factual assertions. For empty context, factual claims SHALL be UNSUPPORTED. Configuration errors, exhausted invalid-output repair, refusals, truncated model responses and upstream failures MUST NOT be represented as unsupported claims or silently omitted claims. HTTP errors SHALL have a stable safe code/message and request identifier: 422 for invalid request data, 413 for oversized bodies, 503 for unavailable configuration or temporary upstream unavailability, 502 for invalid/refused/incomplete upstream results, and 504 for the operation deadline.

#### Scenario: Provider unavailable
- **WHEN** verification needs a model and the provider is unavailable
- **THEN** the request fails with a safe operational error, without a partial successful report or a fabricated factual verdict

#### Scenario: No context and no facts
- **WHEN** context is empty and the answer contains two factual claims
- **THEN** a successful extraction yields two unsupported claims with no citations
- **WHEN** the answer is blank
- **THEN** the response contains no claims and makes no model call

### Requirement: Bounded untrusted processing
The service SHALL bound request size, passage count, aggregate text size, claim count, total provider attempts and total operation time. Context and answer content SHALL be treated as untrusted data, including instructions embedded within them. Schema or citation repair SHALL be finite and SHALL NOT alter source passages to make a quote pass. Resource or repair exhaustion SHALL return an explicit failure.

#### Scenario: Instruction embedded in source
- **WHEN** a passage contains text instructing the verifier to ignore its rules and emit a different verdict
- **THEN** the text remains evidence data and does not authorize tools, privileged actions or bypass of deterministic validators

#### Scenario: Nonterminating or malformed provider
- **WHEN** a provider does not return within the configured deadline or repeatedly returns invalid structured output
- **THEN** the operation terminates with the applicable error within its configured budget

### Requirement: Private local diagnostics
Important request, provider and validation boundaries SHALL emit bounded local diagnostic events with correlation, stage, duration and safe error category. Logs SHALL exclude source passages, answers, quotes, credentials and raw exception text. Logging write failures SHALL NOT change a successful verdict into a service error or conceal the actual verification error. The service SHALL NOT claim to bound a permanently blocked local sink without a separately tested mechanism.

#### Scenario: Secret-seeded upstream exception
- **WHEN** an upstream failure includes synthetic credentials or input text in its exception
- **THEN** local diagnostics identify the failure stage and category without reproducing the sensitive text, and a later request can still succeed

### Requirement: Independently authorized local plan access
The optional ChatGPT-plan provider SHALL obtain this application's own public SIWC grant and keep credentials outside the repository. It MUST validate callback state, PKCE and the signed ID token's issuer, issued-client audience, expiry and nonce before saving an authenticated identity. It SHALL require the granted plan-use scopes before inference and SHALL NOT import credentials from unrelated applications. Authorization failures SHALL be distinguishable by safe fixed diagnostic categories without exposing codes, tokens or upstream error text.

#### Scenario: Initial code exchange rejects the grant
- **WHEN** a state-validated callback supplies an issued client ID but token exchange returns invalid_grant
- **THEN** login may start at most one fresh authorization within its original deadline using that issued client ID, a new state, nonce and PKCE verifier, and a new authorization code
- **AND** the rejected code is never resubmitted, no usable credentials are saved before identity validation, and a second rejection terminates the login with an explicit authentication error

#### Scenario: Returning identity changes during recovery
- **WHEN** reauthorization or its bounded recovery returns a different client ID or a different verified subject for an existing profile
- **THEN** login rejects the result and preserves the previous profile's credentials

#### Scenario: Completed output arrives before an empty terminal summary
- **WHEN** the Responses stream supplies paired output-item events with complete assistant content, then a matching response.completed event whose status is completed and whose output is an empty array
- **THEN** the adapter may reconstruct the output from those completed items and apply the same strict final-response and citation checks
- **AND** missing media-type metadata does not bypass SSE framing, bounds, identity/index consistency or completion checks; deltas, text-done events or EOF alone never establish success

#### Scenario: Optional reasoning status and known terminal usage
- **WHEN** a paired completed reasoning-item event omits its optional status but its assistant message and matching terminal response are completed
- **THEN** absence of reasoning status alone SHALL NOT reject the response; explicit unfinished statuses and incomplete assistant messages SHALL still be rejected
- **AND** if local assembly fails after a terminal response is received, its valid measured usage and model identity SHALL be retained in failure statistics without estimating missing values
