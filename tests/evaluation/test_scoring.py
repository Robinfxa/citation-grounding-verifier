import copy

import pytest

from grounding_eval.dataset import load_dataset
from grounding_eval.reporting import dollar_cost
from grounding_eval.scoring import aggregate, evidence_covered, score_case
from grounding_eval.uncertainty import bootstrap


def predictions(case):
    return [{'claim_text': g.claim_text, 'verdict': g.verdict, 'reasoning': 'offline gold fixture',
             'citations': [q.model_dump() for q in g.evidence_sets[0]] if g.evidence_sets else []}
            for g in case.gold_claims]


def test_omissions_extras_duplicates_and_verdict_blind_matching():
    case = load_dataset()[0]
    full = predictions(case)
    wrong = {**full[0], 'verdict': 'CONTRADICTED'}
    summary = aggregate([score_case(case, [wrong, full[0]])])
    assert summary['counts']['matched'] == 1
    assert summary['counts']['label_correct'] == 0
    assert summary['strict_decomposition']['recall']['value'] == .5
    assert summary['joint_label']['f1']['value'] == 0
    assert summary['confusion']['EXTRA']['SUPPORTED'] == 1
    assert summary['confusion']['SUPPORTED']['MISSING'] == 1


@pytest.mark.parametrize('replacement', ['17', '18', 'oriva', 'not '])
def test_no_fuzzy_matching_for_changed_numbers_case_or_negation(replacement):
    case = load_dataset()[0]
    p = predictions(case)[0]
    p['claim_text'] = replacement + p['claim_text']
    assert score_case(case, [p])['counts']['matched'] == 0


def test_whitespace_only_alias_and_punctuation_preservation():
    case = load_dataset()[1]
    p = predictions(case)
    p[1]['claim_text'] = '\n ' + case.gold_claims[1].aliases[0].replace(' ', '  ') + ' '
    assert score_case(case, p)['counts']['matched'] == 2
    p[1]['claim_text'] = p[1]['claim_text'].replace('.', '')
    assert score_case(case, p)['counts']['matched'] == 1


def test_multi_passage_requires_actual_returned_quote_text_and_every_member():
    case = next(c for c in load_dataset() if c.id == 'thalen-route')
    p = predictions(case)[0]
    assert evidence_covered(case.gold_claims[0], p, case.context_passages)
    p['citations'].pop()
    assert not evidence_covered(case.gold_claims[0], p, case.context_passages)
    p['citations'].append({'index': 1, 'quote': 'Thalen Route'})
    assert not evidence_covered(case.gold_claims[0], p, case.context_passages)
    p['citations'][1]['quote'] = case.context_passages[1]
    assert evidence_covered(case.gold_claims[0], p, case.context_passages)


def test_evidence_alternatives_are_or_of_and_and_quote_is_not_normalized():
    case = load_dataset()[0]
    data = case.model_dump()
    data['gold_claims'][0]['evidence_sets'].append([{'index': 0, 'quote': case.context_passages[0]}])
    case = type(case).model_validate(data)
    p = predictions(case)[0]
    assert evidence_covered(case.gold_claims[0], p, case.context_passages)
    p['citations'][0]['quote'] = p['citations'][0]['quote'].lower()
    assert not evidence_covered(case.gold_claims[0], p, case.context_passages)


def test_failures_keep_all_gold_and_request_denominators():
    case = load_dataset()[0]
    result = aggregate([score_case(case, [], error='deadline_exceeded')])
    assert result['counts']['gold'] == 2
    assert result['request_success']['value'] == 0
    assert result['joint_evidence']['precision']['value'] is None
    assert result['joint_evidence']['recall']['value'] == 0
    assert result['joint_evidence']['f1']['value'] == 0
    assert result['confusion']['SUPPORTED']['ERROR'] == 2
    assert result['case_exact']['value'] == 0


def test_oracle_identity_is_stricter_than_end_to_end_aliases():
    case = load_dataset()[1]
    p = predictions(case)
    p[1]['claim_text'] = case.gold_claims[1].aliases[0]
    assert score_case(case, p)['counts']['matched'] == 2
    score = score_case(case, p, track='oracle')
    assert score['error'] == 'oracle_identity_violation'
    assert score['counts']['gold'] == 2 and score['counts']['predicted'] == 0
    assert score['rejected_predictions'] == p


def test_empty_case_does_not_invent_perfect_claim_metrics():
    case = next(c for c in load_dataset(load_dataset.__defaults__[0].with_name('diagnostic.jsonl')) if not c.gold_claims)
    result = aggregate([score_case(case, [])])
    assert result['case_exact']['value'] == 1
    assert result['joint_evidence']['f1']['value'] is None
    assert result['literal_citation_validity']['value'] is None
    assert result['macro_f1'] is None


def test_citation_deduplication_literal_validity_and_irrelevant_quote_precision():
    case = load_dataset()[0]
    p = predictions(case)
    p[0]['citations'] *= 2
    p[0]['citations'].append(copy.deepcopy(p[1]['citations'][0]))
    result = aggregate([score_case(case, p)])
    assert result['counts']['citation_total'] == 3
    assert result['literal_citation_validity']['value'] == 1
    assert result['gold_relevant_citation_precision']['value'] == pytest.approx(2/3)


def test_seeded_bootstrap_and_paired_cluster_delta():
    cases = load_dataset()[:3]
    good = [score_case(c, predictions(c)) for c in cases]
    bad = [score_case(c, [], error='internal_error') for c in cases]
    a = bootstrap(good, paired_scores=bad, seed=8, samples=120)
    assert a == bootstrap(good, paired_scores=bad, seed=8, samples=120)
    interval = a['intervals']['joint_evidence_f1']
    assert interval['low'] == interval['high'] == 1
    assert interval['degenerate']
    same_family = copy.deepcopy(good)
    same_family[1]['family_id'] = same_family[0]['family_id']
    assert bootstrap(same_family, seed=8, samples=10)['independent_units'] == 2
    with pytest.raises(ValueError, match='population'):
        bootstrap(good, paired_scores=bad[:-1], seed=8, samples=10)


def test_codex_usage_never_becomes_dollar_cost_even_with_prices():
    records = [{'stats': {'provider': 'codex'}}]
    prices = {'provider': 'codex', 'input_per_million': 2, 'output_per_million': 10}
    assert dollar_cost(records, prices) == {
        'value': None, 'currency': 'USD', 'reason': 'subscription_usage_not_dollar_cost'}


def test_irrelevant_extra_citation_prevents_exact_case_success():
    case = load_dataset()[0]
    p = predictions(case)
    p[0]['citations'].append(copy.deepcopy(p[1]['citations'][0]))
    result = aggregate([score_case(case, p)])
    assert result['gold_evidence_coverage']['value'] == 1
    assert result['case_exact']['value'] == 0


def test_paired_interval_includes_observed_delta_not_just_bounds():
    case = load_dataset()[0]
    good = [score_case(case, predictions(case))]
    bad = [score_case(case, [], error='internal_error')]
    result = bootstrap(good, paired_scores=bad, seed=1, samples=20)
    assert result['intervals']['joint_evidence_f1']['estimate'] == 1
