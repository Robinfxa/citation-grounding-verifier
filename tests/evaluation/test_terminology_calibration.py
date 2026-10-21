"""Similar terminology with different meaning must retain strict FP/FN counts."""
import pytest

from grounding_eval.dataset import Case
from grounding_eval.scoring import aggregate, score_case


@pytest.mark.parametrize(('first', 'second', 'definitions'), [
    ('The maximum number of attempts is three.',
     'The maximum number of retries is three.',
     'Attempts include the initial call; retries count only calls after the initial call.'),
    ('The timeout starts at submission.',
     'The timeout starts at execution.',
     'Submission and execution are distinct times separated by a queue wait. The timeout starts exactly once.'),
], ids=['attempts-retries', 'submission-execution'])
@pytest.mark.parametrize('reverse', [False, True], ids=['forward', 'reverse'])
def test_single_term_substitution_does_not_match_or_remove_denominators(first, second, definitions, reverse):
    gold_text, changed_text = (second, first) if reverse else (first, second)
    case = Case.model_validate({
        'id': 'terminology-calibration', 'family_id': 'terminology-calibration',
        'split': 'dev', 'category': 'supported', 'tags': ['calibration'],
        'provenance': {'kind': 'original_fixture', 'authorship': 'agent_authored',
                       'language': 'en', 'fictional': True},
        'context_passages': [gold_text + ' ' + definitions], 'generated_answer': gold_text,
        'gold_claims': [{'id': 'c1', 'claim_text': gold_text, 'aliases': [], 'verdict': 'SUPPORTED',
                         'evidence_sets': [[{'index': 0, 'quote': gold_text}]],
                         'rationale': 'The exact stage or counting unit is stated in context.'}],
    })
    prediction = {'claim_text': gold_text, 'verdict': 'SUPPORTED', 'reasoning': 'Calibration.',
                  'citations': [{'index': 0, 'quote': gold_text}]}
    exact = aggregate([score_case(case, [prediction], track='end-to-end')])
    assert exact['counts']['gold'] == exact['counts']['predicted'] == exact['counts']['matched'] == 1
    assert exact['joint_label']['f1'] == {'numerator': 2, 'denominator': 2, 'value': 1}
    assert exact['joint_evidence']['f1']['value'] == 1

    substituted = aggregate([score_case(case, [{**prediction, 'claim_text': changed_text}], track='end-to-end')])
    assert substituted['counts']['gold'] == substituted['counts']['predicted'] == 1
    assert substituted['counts']['matched'] == 0
    assert substituted['counts']['omitted'] == substituted['counts']['extra'] == 1
    for metric in ('strict_decomposition', 'joint_label', 'joint_evidence'):
        assert substituted[metric]['precision'] == {'numerator': 0, 'denominator': 1, 'value': 0}
        assert substituted[metric]['recall'] == {'numerator': 0, 'denominator': 1, 'value': 0}
        assert substituted[metric]['f1'] == {'numerator': 0, 'denominator': 2, 'value': 0}
