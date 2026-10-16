import copy
from pathlib import Path

import pytest

from grounding_eval.dataset import load_dataset
from grounding_eval.repeated import analyze_repeated
from grounding_eval.scoring import aggregate, evidence_covered, score_case
from grounding_eval.uncertainty import bootstrap

CALIBRATION = Path(__file__).parent / 'fixtures' / 'measurement-calibration.jsonl'


def predictions(case):
    return [{'claim_text': gold.claim_text, 'verdict': gold.verdict, 'reasoning': 'Calibration.',
             'citations': [c.model_dump() for c in gold.evidence_sets[0]] if gold.evidence_sets else []}
            for gold in case.gold_claims]


def test_false_support_uses_all_non_supported_gold_with_missing_and_failure_visible():
    case = load_dataset(CALIBRATION)[0]
    output = predictions(case)[:3]
    output[1]['verdict'] = output[2]['verdict'] = 'SUPPORTED'
    output[2]['citations'] = copy.deepcopy(output[0]['citations'])
    result = aggregate([score_case(case, output)])
    assert result['false_support_rate'] == {'numerator': 2, 'denominator': 3, 'value': 2 / 3}
    assert result['non_supported_judgment_coverage']['value'] == 2 / 3
    assert result['extraction_diagnostics']['omitted_gold'] == 1
    failed = aggregate([score_case(case, [], error='attempt_budget_exhausted')])
    assert failed['false_support_rate'] == {'numerator': 0, 'denominator': 3, 'value': 0}
    assert failed['non_supported_judgment_coverage']['value'] == 0
    assert failed['request_success']['value'] == 0
    assert failed['extraction_diagnostics']['omitted_gold'] == 4
    assert failed['confusion']['CONTRADICTED']['ERROR'] == 2


def test_duplicate_aliases_and_unknown_duplicate_text_never_replace_first_judgment():
    case = load_dataset(CALIBRATION)[0]
    p = predictions(case)[0]
    wrong = {**p, 'verdict': 'CONTRADICTED'}
    alias = {**p, 'claim_text': case.gold_claims[0].aliases[0]}
    unknown = {**p, 'claim_text': 'A novel claim absent from gold.'}
    result = aggregate([score_case(case, [wrong, alias, unknown, unknown])])
    assert result['counts']['matched'] == 1 and result['counts']['label_correct'] == 0
    assert result['extraction_diagnostics'] | {} == {
        'omitted_gold': 3, 'extra_predictions': 3, 'duplicate_predictions': 2,
        'note': result['extraction_diagnostics']['note'],
    }


@pytest.mark.parametrize('text', [
    'Rhea queue can hold eight messages.', 'Rhea queue supports capacity 7.',
    'Rhea queue does not support capacity 8.', 'rhea queue supports capacity 8.',
    'Rhea queue supports capacity 8', 'Paid clients may send messages.',
    'Rhea queue supports capacity 8 and encrypts messages.',
])
def test_unregistered_paraphrase_and_changed_scope_stay_strict_extras(text):
    case = load_dataset(CALIBRATION)[0]
    p = {**predictions(case)[0], 'claim_text': text}
    score = score_case(case, [p])
    assert score['counts']['matched'] == 0 and score['counts']['omitted'] == 4
    assert score['counts']['extra'] == 1


def test_multispan_quote_coverage_and_quote_economy_are_separate_from_semantics():
    case = load_dataset(CALIBRATION)[1]
    p = predictions(case)
    covered = aggregate([score_case(case, p)])
    assert covered['gold_evidence_coverage']['value'] == 1
    for mutation in ('missing', 'partial', 'irrelevant_entity'):
        changed = copy.deepcopy(p[0])
        if mutation == 'missing':
            changed['citations'].pop()
        elif mutation == 'partial':
            changed['citations'][1]['quote'] = 'Hub A stores readings'
        else:
            changed['citations'][1]['quote'] = 'Hub B stores readings for one day.'
        assert not evidence_covered(case.gold_claims[0], changed, case.context_passages)
    broad = copy.deepcopy(p)
    for prediction in broad:
        prediction['citations'][1]['quote'] = case.context_passages[1]
    result = aggregate([score_case(case, broad)])
    assert result['gold_evidence_coverage']['value'] == 1
    assert (result['quote_characters_per_covered_non_unsupported_claim']['value']
            > covered['quote_characters_per_covered_non_unsupported_claim']['value'])
    decomposed = copy.deepcopy(p)
    decomposed[0]['claim_text'] = decomposed[0]['claim_text'].replace('é', 'e\u0301')
    assert score_case(case, decomposed)['counts']['matched'] == 1


def repeated_fixtures():
    cases = load_dataset(CALIBRATION)
    config = {
        'schema_version': '2', 'dataset_version': 'calibration', 'annotation_version': 'frozen-1',
        'scorer_version': '2', 'dataset_sha256': 'frozen-calibration',
        'fingerprints': {'code_sha256': 'fixed', 'prompt_files': {'prompts': 'fixed'}},
        'settings': {'provider': 'offline', 'model': 'fixed', 'max_provider_attempts': 3},
        'measurement_kind': 'offline_protocol_fixture', 'split': 'dev',
        'execution': {'order': 'seeded_job_shuffle'}, 'approaches': ['optimized', 'minimal'],
        'tracks': ['end-to-end'], 'case_ids': [case.id for case in cases],
    }
    result = []
    for repetition in (1, 2, 3):
        records = []
        for case in cases:
            for method in config['approaches']:
                records.append({
                    'case_id': case.id, 'family_id': case.family_id, 'approach': method,
                    'track': 'end-to-end',
                    'score': score_case(case, predictions(case) if method == 'optimized' else [],
                                        error=None if method == 'optimized' else 'upstream_timeout'),
                })
        result.append({'repetition': repetition, 'config': copy.deepcopy(config), 'records': records})
    return result


def test_repeated_pairing_resamples_whole_source_families_and_all_repeats():
    runs = repeated_fixtures()
    ids = runs[0]['config']['case_ids']
    result = analyze_repeated(runs, case_ids=ids, approach='optimized', baseline='minimal',
                              track='end-to-end', seed=9, samples=60)
    assert result['population']['observations'] == 6
    assert result['population']['independent_families'] == 2
    assert result['uncertainty']['independent_units'] == 2
    assert result['uncertainty']['repetitions'] == [1, 2, 3]
    assert result['uncertainty']['intervals']['joint_label_f1']['low'] == 1
    assert len(result['per_repetition']) == 3


def test_full_run_plus_two_subset_runs_reports_only_subset_population():
    runs = repeated_fixtures()
    selected = [runs[0]['config']['case_ids'][0]]
    for run in runs[1:]:
        run['config']['case_ids'] = selected
        run['records'] = [record for record in run['records'] if record['case_id'] in selected]
    result = analyze_repeated(runs, case_ids=selected, approach='optimized', baseline='minimal',
                              track='end-to-end', seed=9, samples=10)
    assert result['population']['kind'] == 'preselected_subset'
    assert result['population']['cases'] == 1 and result['population']['observations'] == 3
    assert result['population']['independent_families'] == 1
    with pytest.raises(ValueError, match='population'):
        analyze_repeated(runs, case_ids=runs[0]['config']['case_ids'], approach='optimized',
                         baseline='minimal', track='end-to-end', seed=9, samples=10)


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'repeat', 'model', 'prompt', 'family'])
def test_repeated_analysis_rejects_missing_pairs_and_incompatible_controls(defect):
    runs = repeated_fixtures()
    ids = runs[0]['config']['case_ids']
    if defect == 'missing':
        runs[1]['records'].pop()
    elif defect == 'duplicate':
        runs[1]['records'].append(copy.deepcopy(runs[1]['records'][0]))
    elif defect == 'repeat':
        runs[1]['repetition'] = 1
    elif defect == 'model':
        runs[1]['config']['settings']['model'] = 'different'
    elif defect == 'prompt':
        runs[1]['config']['fingerprints']['prompt_files']['prompts'] = 'changed'
    else:
        runs[1]['records'][0]['family_id'] = 'different'
    with pytest.raises(ValueError):
        analyze_repeated(runs, case_ids=ids, approach='optimized', baseline='minimal',
                         track='end-to-end', seed=9, samples=10)


def test_bootstrap_rejects_duplicate_case_repeat_even_on_unpaired_input():
    case = load_dataset(CALIBRATION)[0]
    score = {**score_case(case, predictions(case)), 'repetition': 1}
    with pytest.raises(ValueError, match='population'):
        bootstrap([score, score], seed=1, samples=3)
    other = {**score, 'repetition': 2}
    assert bootstrap([score, other], seed=1, samples=3)['independent_units'] == 1
    with pytest.raises(ValueError, match='population'):
        bootstrap([score, other], paired_scores=[score], seed=1, samples=3)
