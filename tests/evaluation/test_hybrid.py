import json
import os
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from grounding.config import Settings
from grounding.contracts import (
    ChoiceDecision,
    ClaimDecisionTrace,
    ProviderAttempt,
    RunStats,
    TokenUsage,
    VerificationError,
    VerificationReport,
    VerificationRun,
)
from grounding_eval.dataset import file_hash, load_dataset
from grounding_eval.runner import (
    EvaluationError,
    SavedStats,
    public_settings,
    regenerate_report,
    run_benchmark,
)

BUDGET = {'provider_attempts': {'typesafe': 60, 'codex': 60},
          'dollar_policy': 'measured_only_no_hard_limit'}
PRICE = {'provider': 'typesafe', 'model': 'jev-1.14.0', 'currency': 'USD',
         'input_per_million': 1.0, 'cached_input_per_million': 0.0, 'output_per_million': 0.0,
         'source': 'offline price fixture', 'as_of': '2026-10-20'}


def choice(label, options=('SUPPORTED', 'CONTRADICTED', 'UNSUPPORTED'), confidence=1.0):
    top = confidence*(1-1/len(options))+1/len(options)
    return ChoiceDecision(label, confidence, {key: top if key == label else (1-top)/(len(options)-1)
                                              for key in options})


class ScriptedHybrid:
    """Evaluation protocol fixture only; no network or credential access."""
    def __init__(self, case, *, fail=False, unknown=False, unaligned=False):
        self.case, self.fail, self.unknown, self.unaligned = case, fail, unknown, unaligned
        self.calls = 0

    async def verify(self, request):
        return await self.result()

    async def verify_claims(self, context_passages, claims):
        return await self.result()

    async def result(self):
        self.calls += 1
        attempts = (
            ProviderAttempt('jev_relation', 'typesafe', 'jev-1.14.0', ('jev-1.14.0',),
                            usage=TokenUsage(100, 2, complete=not self.unknown), question_count=9),
            ProviderAttempt('jev_evidence', 'typesafe', 'jev-1.14.0', ('jev-1.14.0',),
                            usage=TokenUsage(30, 1), question_count=1),
            ProviderAttempt('fallback', 'codex', 'fixed-llm', ('fixed-llm',),
                            outcome='failure' if self.fail else 'success', usage=TokenUsage(50, 10),
                            error_code='upstream_timeout' if self.fail else None),
        )
        traces = []
        claims = []
        for index, gold in enumerate(self.case.gold_claims):
            relation = choice(gold.verdict, confidence=.6 if index == 1 else 1.0)
            traces.append(ClaimDecisionTrace(
                index, relation=relation,
                selection=choice('b0', ('b0', 'NO_ADEQUATE_BUNDLE')) if gold.evidence_sets else None,
                evidence=choice(gold.verdict) if index == 0 else None,
                unsupported_reason=choice('INSUFFICIENT_EVIDENCE', ('INSUFFICIENT_EVIDENCE', 'UNRESOLVED_CONFLICT'))
                if not gold.evidence_sets else None,
                fallback_reason='label_uncertain' if index == 1 else None,
                final_origin=(None if self.fail else 'llm') if index == 1 else 'jev'))
            claims.append({'claim_text': gold.claim_text + (' plural' if index == 0 and self.unaligned else ''),
                           'verdict': gold.verdict, 'reasoning': 'Offline scripted fixture.',
                           'citations': [x.model_dump() for x in gold.evidence_sets[0]] if gold.evidence_sets else []})
        usage = TokenUsage(complete=True)
        for attempt in attempts:
            usage += attempt.usage
        stats = RunStats(provider='hybrid', provider_calls=len(attempts), usage=usage,
                         response_models=('jev-1.14.0', 'fixed-llm'), attempts=attempts,
                         claim_decisions=tuple(traces))
        if self.fail:
            raise VerificationError('upstream_timeout', stats=stats)
        return VerificationRun(VerificationReport.model_validate({'claims': claims}), stats)

    async def aclose(self):
        pass


async def measured(v2_fixture, tmp_path, **kwargs):
    path, _, _ = v2_fixture
    case = load_dataset(path)[0]
    client = kwargs.pop('client', ScriptedHybrid(case))
    return await run_benchmark(
        dataset_path=path, output=tmp_path/'run', approaches=['jev_minimal'], split='dev',
        track='end-to-end', bootstrap_samples=10,
        settings=Settings(provider='codex', model='fixed-llm', diagnostics=False, max_provider_attempts=3),
        verifiers={'jev_minimal': client}, format_version=3, max_total_provider_attempts=60,
        provider_budgets=BUDGET, prices=[PRICE], **kwargs)


def test_added_runtime_fields_do_not_enter_legacy_saved_stats():
    from grounding_eval.runner import serialize_stats

    saved = serialize_stats(RunStats(), format_version=2)
    assert set(saved) == set(SavedStats.model_fields)
    assert 'attempts' not in saved and 'claim_decisions' not in saved


@pytest.mark.parametrize('approaches,expected', [('minimal,optimized', False), ('jev_minimal', True),
                                               ('minimal,jev_optimized', True)])
def test_cli_loads_jev_configuration_only_for_explicit_methods(tmp_path, approaches, expected):
    from unittest.mock import patch

    from grounding_eval import cli

    async def unavailable(**kwargs):
        raise EvaluationError('invalid_arguments')

    with patch.object(Settings, 'from_env', return_value=Settings()) as loader, \
            patch.object(cli, 'run_benchmark', unavailable):
        assert cli.main(['run', '--approaches', approaches, '--output', str(tmp_path/'unused')]) == 2
    loader.assert_called_once_with(include_jev=expected)


def test_hybrid_config_is_explicit_and_contains_no_credentials():
    from grounding_eval.hybrid import experiment_settings

    settings = Settings(provider='codex', model='fixed-llm', api_key='FAKE_SECRET',
                        jev_api_key='FAKE_SECRET', jev_base_url='https://FAKE_SECRET',
                        auth_dir='/FAKE_SECRET')
    value = experiment_settings(settings)
    assert value['jev']['model'] == 'jev-1.14.0'
    assert value['llm']['max_output_tokens']['effective'] is None
    assert 'FAKE_SECRET' not in json.dumps(value)
    assert set(public_settings(settings)) == set(public_settings(Settings()))


async def test_mixed_usage_cost_confidence_and_exact_replay(v2_fixture, tmp_path):
    summary = await measured(v2_fixture, tmp_path)
    group = summary['groups']['jev_minimal/end-to-end']
    assert group['quality']['case_exact']['value'] == 1
    r = group['resources']
    assert r['provider_calls_known'] == 3 and r['questions'] == 10
    assert r['total_usage'] == {'input_tokens': 180, 'output_tokens': 13, 'cached_input_tokens': 0}
    assert r['dollar_cost']['known_subtotal'] == pytest.approx(.00013)
    assert r['dollar_cost']['value'] is None
    assert [(s['provider'], s['attempts']) for s in r['stages']] == [('codex', 1), ('typesafe', 1), ('typesafe', 1)]
    routing = group['routing']
    assert routing['automatic_gold_coverage']['value'] == 2/3
    assert routing['conditional_label_error_aligned']['value'] == 0
    assert routing['fallback_reasons'] == {'label_uncertain': 1}
    assert routing['fallback_outcomes'] == {'success': 1}
    output = tmp_path/'run'
    before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    assert regenerate_report(output) == summary
    assert all((output/name).read_bytes() == value for name, value in before.items())
    record = json.loads((output/'records.jsonl').read_text())
    decision = record['stats']['claim_decisions'][0]['relation']
    assert decision['derived_confidence'] == decision['gate_score'] == 1
    assert decision['threshold'] == .8 and decision['passes_threshold'] is True


@pytest.mark.parametrize('failure,unknown', [(True, False), (False, True)])
async def test_error_denominators_and_unknown_usage(v2_fixture, tmp_path, failure, unknown):
    case = load_dataset(v2_fixture[0])[0]
    summary = await measured(v2_fixture, tmp_path, client=ScriptedHybrid(case, fail=failure, unknown=unknown))
    group = summary['groups']['jev_minimal/end-to-end']
    assert group['failure_inclusive_quality']['counts']['gold'] == 3
    if failure:
        assert group['request_success']['value'] == 0
        assert group['routing']['fallback_outcomes'] == {'unresolved_or_failed': 1}
        assert group['routing']['automatic_gold_coverage']['numerator'] == 0
    else:
        assert group['resources']['total_usage'] is None
    assert group['resources']['dollar_cost']['value'] is None
    assert regenerate_report(tmp_path/'run') == summary


async def test_provider_allocations_stop_before_next_operation_and_keep_gold(v2_fixture, tmp_path):
    path = v2_fixture[0]
    case = load_dataset(path)[0]
    summary = await run_benchmark(
        dataset_path=path, output=tmp_path/'run', approaches=['jev_minimal', 'jev_optimized'],
        split='dev', track='both', settings=Settings(provider='codex', model='fixed-llm',
                                                    diagnostics=False, max_provider_attempts=3),
        bootstrap_samples=5, max_total_provider_attempts=12, format_version=3,
        provider_budgets={**BUDGET, 'provider_attempts': {'typesafe': 3, 'codex': 3}},
        verifiers={name: ScriptedHybrid(case) for name in ['jev_minimal', 'jev_optimized']})
    records = [json.loads(line) for line in (tmp_path/'run/records.jsonl').read_text().splitlines()]
    assert sum(r['attempted'] for r in records) == 1
    assert all(r['error_code'] == 'attempt_budget_exhausted' for r in records[1:])
    assert sum(g['failure_inclusive_quality']['counts']['gold'] for g in summary['groups'].values()) == 12
    assert regenerate_report(tmp_path/'run') == summary


async def test_development_sweep_is_observed_only_and_alignment_is_conservative(v2_fixture, tmp_path):
    from grounding_eval.confidence import threshold_sweep, validate_controlled_comparison
    from grounding_eval.runner import read_saved_run

    case = load_dataset(v2_fixture[0])[0]
    await measured(v2_fixture, tmp_path, client=ScriptedHybrid(case, unaligned=True))
    config, records, cases, _ = read_saved_run(tmp_path/'run')
    sweep = threshold_sweep(config, records, cases, [.5, .8, 1.0])
    assert sweep['fallback_results'] is sweep['whole_pipeline_quality'] is sweep['counterfactual_cost'] is None
    lower = sweep['rows'][0]['groups']['jev_minimal/end-to-end']
    assert lower['sweep_routes']['unobserved_quote_check'] == 1
    assert lower['counts']['automatic_unaligned'] == 1
    assert lower['automatic_gold_coverage']['value'] == 1/3
    validate_controlled_comparison([config, config])
    other = json.loads(json.dumps(config))
    other['experiment']['jev']['label_threshold'] = .9
    with pytest.raises(ValueError, match='incompatible_controlled'):
        validate_controlled_comparison([config, other])
    with pytest.raises(ValueError, match='development_sweep_only'):
        threshold_sweep(config, records, [replace_case_split(cases[0])], [.8])


def replace_case_split(case):
    return case.model_copy(update={'split': 'test'})


@pytest.mark.parametrize('field,value', [
    ('gate_score', .5), ('derived_confidence', .5), ('confidence', True),
    ('probabilities', {'SUPPORTED': True, 'CONTRADICTED': 0, 'UNSUPPORTED': 0}),
])
def test_strict_decision_rejects_tampered_scores(field, value):
    from grounding_eval.hybrid import Decision

    raw = choice('SUPPORTED')
    data = {**asdict(raw), 'derived_confidence': raw.derived_confidence, 'gate_score': raw.gate_score}
    data.update(threshold=.8, passes_threshold=True)
    data[field] = value
    with pytest.raises(ValueError):
        Decision.model_validate(data)


def test_hard_dollar_cap_is_rejected_instead_of_claiming_enforcement():
    from grounding_eval.hybrid import Budget

    with pytest.raises(ValueError):
        Budget.model_validate({**BUDGET, 'max_spend_usd': 1})


@pytest.mark.parametrize('change', ['derived_score', 'missing_score', 'model', 'trace_identity'])
async def test_new_replay_remains_strict_after_artifact_hashes_are_recomputed(v2_fixture, tmp_path, change):
    await measured(v2_fixture, tmp_path)
    output = tmp_path/'run'
    before = (output/'summary.json').read_bytes()
    record = json.loads((output/'records.jsonl').read_text())
    if change == 'derived_score':
        record['stats']['claim_decisions'][0]['relation']['gate_score'] = .9
    elif change == 'missing_score':
        del record['stats']['claim_decisions'][0]['relation']['confidence']
    elif change == 'model':
        record['stats']['attempts'][0]['response_models'] = ['jev-moving-alias']
    else:
        record['stats']['claim_decisions'][0]['claim_id'] = 63
    (output/'records.jsonl').write_text(json.dumps(record)+'\n')
    completion = json.loads((output/'completion.json').read_text())
    completion['records_sha256'] = file_hash(output/'records.jsonl')
    (output/'completion.json').write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)
    assert (output/'summary.json').read_bytes() == before


async def test_absent_traces_are_explicit_and_do_not_get_automatic_credit(v2_fixture, tmp_path):
    case = load_dataset(v2_fixture[0])[0]

    class MissingTrace(ScriptedHybrid):
        async def result(self):
            result = await super().result()
            return VerificationRun(result.report, replace(result.stats, claim_decisions=()))

    summary = await measured(v2_fixture, tmp_path, client=MissingTrace(case))
    routing = summary['groups']['jev_minimal/end-to-end']['routing']
    assert routing['counts']['predictions_missing_trace'] == 3
    assert routing['automatic_gold_coverage']['value'] == 0
    assert routing['conditional_label_error_aligned']['value'] is None


@pytest.mark.parametrize('driver_name', ['hybrid_cli_fixture.py', 'hybrid_runtime_fixture.py'])
def test_actual_cli_hybrid_success_failure_recovery_replay_sweep(v2_fixture, tmp_path, driver_name):
    path = v2_fixture[0]
    budget = tmp_path/'budget.json'
    price = tmp_path/'prices.json'
    budget.write_text(json.dumps(BUDGET))
    price.write_text(json.dumps([PRICE]))
    driver = Path(__file__).with_name(driver_name)
    env = {'PATH': os.defpath, 'PYTHONPATH': str(Path(__file__).resolve().parents[2]/'src')}

    def invoke(scenario, args):
        result = subprocess.run([sys.executable, str(driver), scenario, str(path), *map(str, args)],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
        assert 'FAKE_JEV_SECRET' not in result.stdout+result.stderr
        assert 'FORGED_JEV' not in result.stdout+result.stderr
        return result, json.loads(result.stdout)

    def arguments(output, **overrides):
        return ['run', '--dataset', path, '--approaches', 'jev_minimal,jev_optimized', '--split', 'dev',
                '--track', 'both', '--format-version', str(overrides.get('format_version', 3)),
                '--max-total-provider-attempts', '60', '--provider-budgets', budget,
                '--prices', price, '--bootstrap-samples', '5', '--output', output, '--stop-on-model-error']

    output = tmp_path/'success'
    result, summary = invoke('success', arguments(output))
    assert result.returncode == 0, result.stdout+result.stderr
    assert summary['measurement_kind'] == 'offline_protocol_fixture'
    assert summary['format_version'] == 3 and summary['completion']['record_count'] == 4
    assert set(summary['paired_jev_optimized_minus_jev_minimal']) == {'oracle', 'end-to-end'}
    before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    replay, saved = invoke('success', ['report', output])
    assert replay.returncode == 0 and saved == summary
    assert all((output/name).read_bytes() == value for name, value in before.items())
    sweep, analysis = invoke('success', ['sweep', output, '--thresholds', '.5,.8,.9'])
    assert sweep.returncode == 0 and analysis['counterfactual_cost'] is None
    assert all((output/name).read_bytes() == value for name, value in before.items())
    failure, failed = invoke('failure', arguments(tmp_path/'failure'))
    assert failure.returncode == 2 and failed['completion']['status'] == 'COMPLETED_WITH_ERRORS'
    assert sum(g['failure_inclusive_quality']['counts']['gold'] for g in failed['groups'].values()) == 12
    assert all(g['errors'] == {'upstream_timeout': 1} for g in failed['groups'].values())
    recovered, good = invoke('recovery', arguments(tmp_path/'recovered'))
    assert recovered.returncode == 0 and good['completion']['status'] == 'COMPLETE'
    invalid, _ = invoke('success', arguments(tmp_path/'must-not-exist', format_version=2))
    assert invalid.returncode == 2 and not (tmp_path/'must-not-exist').exists()
    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert events[-1]['stage'] == 'eval_run' and events[-1]['completed'] == 4
