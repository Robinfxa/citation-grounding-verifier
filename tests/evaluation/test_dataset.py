import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from grounding_eval.dataset import DEFAULT_DATASET, Case, DatasetError, load_dataset, validate_cases


def test_frozen_layout_and_verdict_support():
    summary = validate_cases(load_dataset(main=True), main=True)
    assert summary['cases'] == 32
    assert summary['splits'] == {'dev': 8, 'test': 24}
    assert all(n >= 12 for n in summary['claims_by_split']['test'].values())
    assert len(load_dataset(DEFAULT_DATASET.with_name('diagnostic.jsonl'))) == 6


@pytest.mark.parametrize('defect', ['quote', 'bool_index', 'unsupported_evidence', 'empty_group', 'alias_collision', 'duplicate_claim'])
def test_bad_annotation_rejected(defect):
    value = copy.deepcopy(load_dataset()[0].model_dump())
    gold = value['gold_claims']
    if defect == 'quote':
        gold[0]['evidence_sets'][0][0]['quote'] += ' forged'
    elif defect == 'bool_index':
        gold[0]['evidence_sets'][0][0]['index'] = False
    elif defect == 'unsupported_evidence':
        gold[0]['verdict'] = 'UNSUPPORTED'
    elif defect == 'empty_group':
        gold[0]['evidence_sets'] = [[]]
    elif defect == 'alias_collision':
        gold[0]['aliases'] = [gold[1]['claim_text']]
    else:
        gold[1]['id'] = gold[0]['id']
    with pytest.raises(ValidationError):
        Case.model_validate(value)


def test_duplicate_case_and_family_leakage_rejected():
    case = load_dataset()[0]
    with pytest.raises(DatasetError, match='duplicate_case'):
        validate_cases([case, case])
    other = case.model_copy(update={'id': 'other', 'split': 'test'})
    with pytest.raises(DatasetError, match='family_crosses'):
        validate_cases([case, other])


def test_load_error_does_not_echo_payload(tmp_path: Path):
    path = tmp_path / 'bad.jsonl'
    path.write_text('{TOP_SECRET')
    with pytest.raises(DatasetError) as caught:
        load_dataset(path)
    assert 'TOP_SECRET' not in str(caught.value)
