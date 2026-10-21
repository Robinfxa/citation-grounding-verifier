"""Exercise the public CLI with only the external provider replaced locally."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from grounding.config import Settings
from grounding_eval.dataset import file_hash, load_dataset
from grounding_eval.runner import EvaluationError, json_text, run_benchmark
from grounding_eval.scoring import score_case

ROOT = Path(__file__).resolve().parents[2]
FAKE_SECRET = 'FAKE_MODEL_SECRET_94'
PROVIDER_CLI = r'''
import json
import runpy
import sys
from pathlib import Path

from grounding.contracts import ProviderResult, TokenUsage, VerificationError
from grounding.providers import OpenAIProvider

mode, calls_path, *args = sys.argv[1:]
calls_path = Path(calls_path)
calls = 0

def initialize(self, *, model, **kwargs):
    self.model = model
    if mode.startswith('init_'):
        code = mode.removeprefix('init_')
        if code == 'internal_error':
            raise RuntimeError('FAKE_MODEL_SECRET_94\nFORGED_MODEL_RECORD')
        if code == 'implementation_unavailable':
            raise ImportError('FAKE_MODEL_SECRET_94\nFORGED_MODEL_RECORD')
        raise VerificationError(code)

async def generate(self, request):
    global calls
    calls += 1
    with calls_path.open('a') as stream:
        stream.write(json.dumps({'call': calls, 'schema': request.schema_name}) + '\n')
    error = mode.removeprefix('after_success_')
    if mode != 'success' and not (mode.startswith('after_success_') and calls == 1):
        if error == 'internal_error':
            raise RuntimeError('FAKE_MODEL_SECRET_94\nFORGED_MODEL_RECORD')
        if error == 'invalid_model_output':
            return ProviderResult('FAKE_MODEL_SECRET_94\nFORGED_MODEL_RECORD',
                                  TokenUsage(7, 3, 1), self.model)
        failure = VerificationError(error)
        failure.add_note('FAKE_MODEL_SECRET_94\nFORGED_MODEL_RECORD')
        raise failure
    answer = request.payload.get('generated_answer', '')
    if request.schema_name == 'atomic_claims':
        result = {'claims': [{'claim_text': answer, 'answer_quote': answer}]}
    elif request.schema_name == 'claim_judgments':
        result = {'judgments': [
            {'claim_id': claim['claim_id'], 'verdict': 'UNSUPPORTED',
             'reasoning': 'Local provider fixture.', 'citations': []}
            for claim in request.payload['claims']]}
    else:
        result = {'claims': [{'claim_text': answer, 'verdict': 'UNSUPPORTED',
                              'reasoning': 'Local provider fixture.', 'citations': []}]}
    return ProviderResult(json.dumps(result), TokenUsage(7, 3, 1), self.model)

async def close(self):
    pass

OpenAIProvider.__init__ = initialize
OpenAIProvider.generate = generate
OpenAIProvider.aclose = close
sys.argv = ['grounding-eval', *args]
runpy.run_module('grounding_eval', run_name='__main__')
'''


def invoke_cli(cwd, *args, mode='success', **environment):
    """Do not inherit credentials or read the workspace's .env."""
    cwd.mkdir(parents=True, exist_ok=True)
    env = {
        'PATH': os.defpath,
        'PYTHONPATH': str(ROOT / 'src'),
        'GROUNDING_PROVIDER': 'openai',
        'GROUNDING_MODEL': 'offline-provider-fixture',
        'OPENAI_API_KEY': 'LOCAL_FAKE_KEY',
        'GROUNDING_MAX_PROVIDER_ATTEMPTS': '3',
        'GROUNDING_TRANSPORT_RETRIES': '1',
        'GROUNDING_RETRY_DELAY': '0',
        **environment,
    }
    return subprocess.run(
        [sys.executable, '-c', PROVIDER_CLI, mode, str(cwd / 'calls.jsonl'),
         *map(str, args)], cwd=cwd, env=env, capture_output=True, text=True, timeout=30)


def run_cli(cwd, dataset, *, mode='success', stop=True, budget=30, track='both', quiet=False):
    args = ['run', '--dataset', dataset, '--approaches', 'minimal,optimized,heuristic',
            '--split', 'dev', '--track', track, '--output', cwd / 'run',
            '--bootstrap-samples', '3', '--seed', '19',
            '--max-total-provider-attempts', budget]
    if stop:
        args.append('--stop-on-model-error')
    if quiet:
        args.append('--quiet')
    return invoke_cli(cwd, *args, mode=mode)


def read_records(cwd):
    return [json.loads(line) for line in (cwd / 'run' / 'records.jsonl').read_text().splitlines()]


def rewrite_state(cwd, *, config=None, records=None):
    output = cwd / 'run'
    if config is not None:
        (output / 'config.json').write_text(json.dumps(config))
    if records is not None:
        (output / 'records.jsonl').write_text(''.join(json.dumps(record) + '\n' for record in records))
    completion = json.loads((output / 'completion.json').read_text())
    completion.update(config_sha256=file_hash(output / 'config.json'),
                      records_sha256=file_hash(output / 'records.jsonl'))
    if records is not None:
        completion['provider_attempts_charged'] = sum(
            record['provider_attempts_charged'] for record in records)
    (output / 'completion.json').write_text(json.dumps(completion))


def test_public_cli_stops_later_models_and_keeps_heuristic_and_denominators(v2_fixture, tmp_path):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'failure'
    result = run_cli(cwd, dataset, mode='upstream_unavailable')
    assert result.returncode == 2, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary['completion']['status'] == 'COMPLETED_WITH_ERRORS'
    records = read_records(cwd)
    model = [record for record in records if record['approach'] != 'heuristic']
    assert len(model) == 4 and sum(record['attempted'] for record in model) == 1
    assert model[0]['status'] == 'ERROR' and model[0]['error_code'] == 'upstream_unavailable'
    assert model[0]['provider_attempts_charged'] == 2
    assert model[0]['stats']['retries'] == 1 and not model[0]['stats']['usage']['complete']
    for record in model[1:]:
        assert record['status'] == 'NOT_RUN' and record['error_code'] == 'upstream_unavailable'
        assert not record['attempted'] and record['stats_known']
        assert record['elapsed_ms'] is None and record['started_at'] is None
        assert record['provider_attempts_reserved'] == record['provider_attempts_charged'] == 0
        assert record['stats']['provider_calls'] == record['stats']['retries'] == record['stats']['repairs'] == 0
        assert record['stats']['latency_ms'] == 0 and record['stats']['response_models'] == []
        assert record['stats']['usage'] == {
            'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0, 'complete': True}
    assert all(record['status'] == 'OK' for record in records if record['approach'] == 'heuristic')
    assert all(record['score']['counts']['gold'] == 3 for record in records)
    assert len((cwd / 'calls.jsonl').read_text().splitlines()) == 2
    assert summary['completion']['provider_attempts_charged'] == 2
    assert json.loads((cwd / 'run' / 'config.json').read_text())['stop_on_model_error'] is True


def test_public_replay_rejects_calls_after_first_model_error(v2_fixture, tmp_path):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'continued'
    result = run_cli(cwd, dataset, mode='upstream_unavailable', stop=False)
    assert result.returncode == 2
    assert sum(record['attempted'] for record in read_records(cwd)) == 6
    config = json.loads((cwd / 'run' / 'config.json').read_text())
    config.update(stop_on_model_error=True, initialization_errors={})
    rewrite_state(cwd, config=config)
    before = (cwd / 'run' / 'summary.json').read_bytes()
    replay = invoke_cli(cwd, 'report', cwd / 'run')
    assert replay.returncode == 2 and json.loads(replay.stdout) == {'error_code': 'run_artifact_invalid'}
    assert (cwd / 'run' / 'summary.json').read_bytes() == before


def replay_unchanged(cwd, expected_exit):
    before = {str(path.relative_to(cwd / 'run')): path.read_bytes()
              for path in (cwd / 'run').rglob('*') if path.is_file()}
    calls = (cwd / 'calls.jsonl').read_bytes() if (cwd / 'calls.jsonl').exists() else b''
    result = invoke_cli(cwd, 'report', cwd / 'run', mode='internal_error')
    assert result.returncode == expected_exit, result.stdout + result.stderr
    assert json.loads(result.stdout) == json.loads((cwd / 'run' / 'summary.json').read_text())
    assert all((cwd / 'run' / name).read_bytes() == data for name, data in before.items())
    assert ((cwd / 'calls.jsonl').read_bytes() if (cwd / 'calls.jsonl').exists() else b'') == calls


@pytest.mark.parametrize('mode,call_count', [
    ('not_configured', 1), ('authentication_failed', 1), ('provider_protocol_error', 1),
    ('invalid_model_output', 1), ('internal_error', 1), ('attempt_budget_exhausted', 1),
    ('quota_exhausted', 1),
])
def test_public_cli_keeps_original_error_class_and_sanitized_diagnostics(
        v2_fixture, tmp_path, mode, call_count):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / mode
    result = run_cli(cwd, dataset, mode=mode)
    assert result.returncode == 2
    records = read_records(cwd)
    model = [record for record in records if record['approach'] != 'heuristic']
    assert sum(record['attempted'] for record in model) == 1
    assert all(record['error_code'] == mode for record in model)
    assert all(record['status'] == 'NOT_RUN' for record in model[1:])
    assert len((cwd / 'calls.jsonl').read_text().splitlines()) == call_count
    emitted = [json.loads(line) for line in result.stderr.splitlines()]
    failed = [event for event in emitted if event.get('error_code') == mode
              and event['request_id'] == model[0]['request_id']]
    assert failed and all(event['outcome'] == 'failure' for event in failed)
    terminal = [event for event in emitted if event['stage'] == 'eval_run' and event['event'] == 'end']
    assert len(terminal) == 1 and terminal[0]['error_code'] == 'request_failures'
    assert terminal[0]['completed'] == terminal[0]['requested'] == len(records)
    assert terminal[0]['failed_requests'] == 4
    assert FAKE_SECRET not in result.stderr + result.stdout
    assert 'FORGED_MODEL_RECORD' not in result.stderr + result.stdout
    assert all(FAKE_SECRET not in path.read_text() for path in (cwd / 'run').rglob('*') if path.is_file())
    replay_unchanged(cwd, 2)


@pytest.mark.parametrize('code', ['not_configured', 'internal_error', 'implementation_unavailable'])
def test_public_cli_initialization_failure_stops_without_any_provider_calls(
        v2_fixture, tmp_path, code):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'initialization'
    result = run_cli(cwd, dataset, mode='init_' + code)
    assert result.returncode == 2
    model = [record for record in read_records(cwd) if record['approach'] != 'heuristic']
    assert len(model) == 4 and all(not record['attempted'] for record in model)
    assert all(record['status'] == 'NOT_RUN' and record['error_code'] == code
               and record['stats_known'] and record['stats']['usage']['complete']
               and record['provider_attempts_charged'] == 0
               and record['stats']['provider_calls'] == 0 for record in model)
    assert json.loads(result.stdout)['completion']['provider_attempts_charged'] == 0
    config = json.loads((cwd / 'run' / 'config.json').read_text())
    assert config['initialization_errors'] == {'minimal': code, 'optimized': code}
    assert not (cwd / 'calls.jsonl').exists()
    assert FAKE_SECRET not in result.stderr + result.stdout
    assert all(record['status'] == 'OK' for record in read_records(cwd)
               if record['approach'] == 'heuristic')
    replay_unchanged(cwd, 2)


def test_public_cli_preserves_success_before_failure_and_new_run_recovers(v2_fixture, tmp_path):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'after-success'
    result = run_cli(cwd, dataset, mode='after_success_upstream_unavailable')
    assert result.returncode == 2
    model = [record for record in read_records(cwd) if record['approach'] != 'heuristic']
    assert model[0]['status'] == 'OK' and model[0]['stats']['usage']['input_tokens'] == 7
    assert model[1]['attempted'] and model[1]['error_code'] == 'upstream_unavailable'
    assert all(not record['attempted'] for record in model[2:])
    assert len((cwd / 'calls.jsonl').read_text().splitlines()) == 3
    replay_unchanged(cwd, 2)
    recovered = tmp_path / 'recovered'
    success = run_cli(recovered, dataset)
    assert success.returncode == 0
    assert json.loads(success.stdout)['completion']['status'] == 'COMPLETE'
    assert all(record['status'] == 'OK' and record['attempted'] for record in read_records(recovered))
    assert len((recovered / 'calls.jsonl').read_text().splitlines()) == 5
    replay_unchanged(recovered, 0)


@pytest.mark.parametrize('mode', ['success', 'upstream_unavailable'])
def test_public_cli_quiet_preserves_outcomes_with_no_diagnostics(v2_fixture, tmp_path, mode):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'quiet'
    result = run_cli(cwd, dataset, mode=mode, quiet=True)
    assert result.returncode == (0 if mode == 'success' else 2)
    assert result.stderr == ''
    records = read_records(cwd)
    assert sum(record['attempted'] for record in records if record['approach'] != 'heuristic') == (
        4 if mode == 'success' else 1)


@pytest.mark.parametrize('mode,budget,error,charged,budget_stopped,quota_stopped', [
    ('upstream_unavailable', 0, 'attempt_budget_exhausted', 0, True, False),
    ('upstream_unavailable', 3, 'attempt_budget_exhausted', 2, True, False),
    ('quota_exhausted', 3, 'quota_exhausted', 1, False, True),
])
def test_public_cli_existing_budget_and_quota_stops_keep_priority(
        v2_fixture, tmp_path, mode, budget, error, charged, budget_stopped, quota_stopped):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'priority'
    result = run_cli(cwd, dataset, mode=mode, budget=budget)
    assert result.returncode == 2
    records = read_records(cwd)
    model = [record for record in records if record['approach'] != 'heuristic']
    assert all(record['error_code'] == error for record in model if not record['attempted'])
    assert all(record['status'] == 'OK' for record in records if record['approach'] == 'heuristic')
    completion = json.loads(result.stdout)['completion']
    assert completion['provider_attempts_charged'] == charged
    assert completion['stopped_after_attempt_budget_exhausted'] is budget_stopped
    assert completion['stopped_after_quota_exhausted'] is quota_stopped
    replay_unchanged(cwd, 2)


def test_omitted_option_continues_and_missing_historical_key_replays_byte_identically(
        v2_fixture, tmp_path):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / 'legacy-default'
    result = run_cli(cwd, dataset, mode='upstream_unavailable', stop=False)
    assert result.returncode == 2
    assert all(record['attempted'] for record in read_records(cwd))
    assert len((cwd / 'calls.jsonl').read_text().splitlines()) == 8
    config = json.loads((cwd / 'run' / 'config.json').read_text())
    assert config.pop('stop_on_model_error') is False
    assert 'initialization_errors' not in config
    rewrite_state(cwd, config=config)
    summary = json.loads(result.stdout)
    summary['completion'] = json.loads((cwd / 'run' / 'completion.json').read_text())
    (cwd / 'run' / 'summary.json').write_text(json_text(summary))
    replay_unchanged(cwd, 2)


@pytest.mark.parametrize('defect', [
    'different_reason', 'skip_without_trigger', 'unknown_stopped_usage', 'invented_tokens',
    'invented_calls', 'missing_initialization_metadata', 'invalid_initialization_code',
    'invalid_initialization_approach', 'invalid_flag',
])
def test_public_replay_rejects_forged_stop_even_after_hashes_and_scores_are_repaired(
        v2_fixture, tmp_path, defect):
    dataset, _, _ = v2_fixture
    cwd = tmp_path / defect
    result = run_cli(cwd, dataset, mode='upstream_unavailable')
    assert result.returncode == 2
    records = read_records(cwd)
    model = [record for record in records if record['approach'] != 'heuristic']
    config = json.loads((cwd / 'run' / 'config.json').read_text())
    if defect == 'different_reason':
        model[1]['error_code'] = 'authentication_failed'
    elif defect == 'skip_without_trigger':
        first = model[0]
        for key in ('status', 'attempted', 'elapsed_ms', 'started_at', 'stats', 'stats_known',
                    'provider_attempts_reserved', 'provider_attempts_charged'):
            first[key] = copy.deepcopy(model[1][key])
    elif defect == 'unknown_stopped_usage':
        model[1]['stats_known'] = False
        model[1]['stats']['usage']['complete'] = False
    elif defect == 'invented_tokens':
        model[1]['stats']['usage']['input_tokens'] = 1
    elif defect == 'invented_calls':
        model[1]['stats']['provider_calls'] = 1
    elif defect == 'missing_initialization_metadata':
        del config['initialization_errors']
    elif defect == 'invalid_initialization_code':
        config['initialization_errors'] = {'minimal': FAKE_SECRET}
    elif defect == 'invalid_initialization_approach':
        config['initialization_errors'] = {'other': 'internal_error'}
    elif defect == 'invalid_flag':
        config['stop_on_model_error'] = 1
    case = load_dataset(dataset)[0]
    for record in records:
        record['score'] = score_case(case, record['report']['claims'] if record['report'] else [],
                                    track=record['track'], error=record['error_code'])
    rewrite_state(cwd, config=config, records=records)
    before = (cwd / 'run' / 'summary.json').read_bytes()
    replay = invoke_cli(cwd, 'report', cwd / 'run')
    assert replay.returncode == 2 and json.loads(replay.stdout) == {'error_code': 'run_artifact_invalid'}
    assert FAKE_SECRET not in replay.stdout + replay.stderr
    assert (cwd / 'run' / 'summary.json').read_bytes() == before


@pytest.mark.parametrize('flag', [None, 1, 'true'])
async def test_library_rejects_non_boolean_stop_policy_before_creating_run(v2_fixture, tmp_path, flag):
    dataset, _, _ = v2_fixture
    with pytest.raises(EvaluationError, match='invalid_arguments'):
        await run_benchmark(dataset_path=dataset, output=tmp_path / 'invalid', approaches=['heuristic'],
                            split='dev', stop_on_model_error=flag, settings=Settings(diagnostics=False))
    assert not (tmp_path / 'invalid').exists()
