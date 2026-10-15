# Inspected primary sources

Access date: 2026-10-15. Papers are primary evidence; repositories below are the authors' implementations. GitHub source links are pinned to the commit resolved and read during research. Stable documentation and author blog pages are mutable and are identified by access date. Static source inspection does not establish a measured failure frequency.

## S1. FActScore

- Min et al., EMNLP 2023: [paper](https://arxiv.org/html/2305.14251v2), [ACL record](https://aclanthology.org/2023.emnlp-main.741/). Grade A. Useful precedent for decomposition and factual precision relative to a knowledge source; its biography/Wikipedia setting differs from a supplied-context HTTP verifier.
- Official implementation: commit `f28272deffcf33efc1f1117d5479c10bb75221a9`, dated 2025-04-13. Read [`AtomicFactGenerator` configuration](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/atomic_facts.py#L20-L26), [entity postprocessing](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/atomic_facts.py#L232-L285), and [binary verification/parser](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/factscorer.py#L209-L261). Grade A, inspected statically. Do not port the biography-specific cleanup, historical provider setup, or permissive support fallback.
- [MIT license](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/LICENSE) inspected. No code copied or dependency proposed.

## S2. RAGAS faithfulness

- Es et al., EACL 2024 demo: [original paper](https://aclanthology.org/2024.eacl-demo.16.pdf). Grade A. [Current faithfulness documentation](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/) inspected, Grade B.
- Official repository moved from `explodinggradients/ragas` to `vibrantlabsai/ragas`. Inspected commit `298b68274234c060deacab3cf5fb52aa3a20e885`, dated 2026-02-24: [two stages, empty-statement NaN, joined contexts](https://github.com/vibrantlabsai/ragas/blob/298b68274234c060deacab3cf5fb52aa3a20e885/src/ragas/metrics/collections/faithfulness/metric.py#L103-L145), [statement/verdict schemas and binary prompt](https://github.com/vibrantlabsai/ragas/blob/298b68274234c060deacab3cf5fb52aa3a20e885/src/ragas/metrics/collections/faithfulness/util.py#L17-L86). Grade A.
- Both explicit refutation and unmentioned facts receive `0` in the examples. Its return score supplies neither this API's three-way labels nor verbatim citation provenance. It also requires a question, unlike the assignment's request schema. Borrow the pipeline pattern rather than assuming the public metric can replace the service.
- [Apache-2.0 license](https://github.com/vibrantlabsai/ragas/blob/298b68274234c060deacab3cf5fb52aa3a20e885/LICENSE) inspected. No import/API compatibility claim is made.

## S3. ALCE

- Gao et al., EMNLP 2023: [paper §3.3 and Appendix E](https://aclanthology.org/2023.emnlp-main.398.pdf), [ACL record](https://aclanthology.org/2023.emnlp-main.398/). Grade A. Evidence-set entailment is directly relevant; the task is cited answer generation rather than this service's three-way classification.
- Official implementation commit `246c476a4edfc564266b7346b6e29ef4861ae937`, dated 2024-10-09: [`compute_autoais`, joint passages and citation precision](https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/eval.py#L341-L418). Grade A. It checks statement-level entailment against cited documents; it does not enforce an exact quotation schema.
- Important limitation: Appendix E describes false penalties for partially relevant redundant citations. Joint sufficiency is useful; leave-one-out necessity is not a universal definition of a valid citation. The large historical NLI model is unnecessary infrastructure for the first small service.
- [MIT license](https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/LICENSE) inspected. No code copied.

## S4. SAFE / LongFact

- Wei et al., 2024: [paper v4](https://arxiv.org/html/2403.18802v4), [DeepMind publication page](https://deepmind.google/research/publications/85420/). Grade A for paper, B for summary.
- Official implementation commit `9d27158d198ced0a9d8271a80147cae580614601`, dated 2024-04-07: [pipeline README](https://github.com/google-deepmind/long-form-factuality/blob/9d27158d198ced0a9d8271a80147cae580614601/eval/safe/README.md), [atomic-fact adapter](https://github.com/google-deepmind/long-form-factuality/blob/9d27158d198ced0a9d8271a80147cae580614601/eval/safe/get_atomic_facts.py), [search/judgment retry loops](https://github.com/google-deepmind/long-form-factuality/blob/9d27158d198ced0a9d8271a80147cae580614601/eval/safe/rate_atomic_fact.py#L148-L185), [failed-fact omission path](https://github.com/google-deepmind/long-form-factuality/blob/9d27158d198ced0a9d8271a80147cae580614601/eval/safe/search_augmented_factuality_eval.py#L149-L178). Grade A.
- SAFE searches external world knowledge and filters relevance to an input question. Both differ from the assignment. Its bounded iteration is useful inspiration; nested retries, silent omission after repeated exceptions, and source-code API-key configuration should not be copied. `num_tries <= max_retries` permits one more attempt than the parameter value, so use an explicit total-call definition.
- [License](https://github.com/google-deepmind/long-form-factuality/blob/9d27158d198ced0a9d8271a80147cae580614601/LICENSE) inspected: bundled FActScore files are MIT; the listed first-party folders are Apache-2.0. No package adoption proposed.

## S5. Claimify

- Metropolitansky and Larson, ACL 2025: [Towards Effective Extraction and Evaluation of Factual Claims, §§2–3](https://aclanthology.org/2025.acl-long.348.pdf). Grade A.
- [Author's Microsoft Research explanation, 2025-03-19](https://www.microsoft.com/en-us/research/blog/claimify-extracting-high-quality-claims-from-language-model-outputs/). Grade B. Inspected the omission, attribution, ambiguity, and condition examples, and the selection/disambiguation/decomposition stages.
- The paper separates extraction entailment, information coverage, and decontextualization. It warns that aggressive atomicity is not itself the end goal. Borrow those evaluation dimensions and condition-preservation principles. Do not silently exclude ambiguous factual sentences merely because this research pipeline excludes them from decomposition: that would hide possible factual content in this assignment. No official extraction package was audited or proposed as a dependency.

## S6. DecompScore

- Wanner et al., *SEM 2024: [A Closer Look at Claim Decomposition](https://aclanthology.org/2024.starsem-1.13.pdf), [ACL record](https://aclanthology.org/2024.starsem-1.13/). Grade A. Read the decomposition failure categories and discussion of the sensitivity of downstream factual precision to the decomposition method.
- Useful distinction: coverage measures omitted facts, coherence measures whether extracted claims match the answer, atomicity measures separation. A higher downstream support score alone does not demonstrate a better verifier. Use independently annotated gold claims rather than importing a claim-count objective that can reward unnecessary splitting. No implementation dependency audited.

## S7. FEVER

- Thorne et al., NAACL 2018: [paper §§3 and 5.5](https://aclanthology.org/N18-1074.pdf), [ACL record](https://aclanthology.org/N18-1074/). Grade A. The source-bound supported/refuted/not-enough-information distinction and sentence-level evidence match the desired label semantics more closely than binary factuality metrics.
- The paper includes composition across sentences/pages and concatenates multiple evidence sentences for entailment. Its Wikipedia retrieval universe is not identical to the request's closed context. It provides no adopted rule for equally credible contradictory passages in this service. Borrow the evidence-relative labels, not external lookup or historical benchmark scores.

## S8. Indirect prompt injection

- Greshake et al., 2023: [Not what you've signed up for, v2](https://arxiv.org/html/2302.12173v2), dated 2023-05-05. Grade A. [Author demonstration repository README](https://github.com/greshake/llm-security/blob/main/README.md) inspected, Grade B as a mutable companion explanation.
- The paper's demonstrated attack surface is instructions carried inside material an application consumes. This justifies hostile context/answer fixtures and an explicit data/instruction boundary. It does not prove that any particular prompt, delimiter, or schema prevents attacks on this verifier; that requires empirical adversarial evaluation. No demonstration payloads or code were executed.
