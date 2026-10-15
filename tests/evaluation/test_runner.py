import asyncio
import json
import os
import subprocess
import sys

import pytest

from grounding.config import Settings
from grounding.contracts import (
    RunStats,
    TokenUsage,
    VerificationError,
    VerificationReport,
    VerificationRun,
)
from grounding_eval.dataset import load_dataset
from grounding_eval.runner import EvaluationError, regenerate_report, run_benchmark


class MemoryVerifier:
    name = 'offline'

    def __init__(self, case, *, error=None, rewrite=False, invalid_quote=False, slow=False):
        self.case = case
        self.error = error
        self.rewrite = rewrite
        self.invalid_quote = invalid_quote
        self.slow = slow
        self.closed = False
        self.inputs = []

    async def verify(self, request):
        self.inputs.append(request)
        return await self.result()

    async def verify_claims(self, context_passages, claims):
        self.inputs.append((list(context_passages), list(claims)))
        return await self.result()

    async def result(self):
        if self.slow:
            await asyncio.sleep(2)
        if self.error:
            raise self.error
        claims = [{'claim_text': g.claim_text, 'verdict': g.verdict, 'reasoning': 'offline fixture',
                   'citations': [c.model_dump() for c in g.evidence_sets[0]] if g.evidence_sets else []}
                  for g in self.case.gold_claims]
        if self.rewrite:
            claims[0]['claim_text'] += ' changed'
        if self.invalid_quote:
            claims[0]['citations'][0]['quote'] = 'not in source'
        return VerificationRun(VerificationReport.model_validate({'claims': claims}),
                               RunStats(provider='codex', requested_model='fixed', response_models=('fixed-returned',),
                                        provider_calls=2, retries=1, repairs=1, usage=TokenUsage(12, 4, 2)))

    async def aclose(self):
        self.closed = True


@pytest.fixture
def fixture(tmp_path):
    case = load_dataset()[0]
    path = tmp_path / 'data.jsonl'
    path.write_text(json.dumps(case.model_dump())+'\n')
    return case, path


def settings(**kwargs):
    return Settings(model='fixed', diagnostics=False, **kwargs)


async def test_runner_protocol_inputs_usage_fingerprints_and_saved_reproduction(tmp_path, fixture):
    case, path = fixture
    verifier = MemoryVerifier(case)
    output = tmp_path / 'run'
    summary = await run_benchmark(dataset_path=path, output=output, approaches=['optimized'],
                                  split='dev', settings=settings(), bootstrap_samples=20,
                                  verifiers={'optimized': verifier})
    assert verifier.closed
    assert (case.context_passages, [g.claim_text for g in case.gold_claims]) in verifier.inputs
    assert summary['measurement_kind'] == 'offline_protocol_fixture'
    for group in summary['groups'].values():
        assert group['quality']['case_exact']['value'] == 1
        assert group['resources']['known_usage']['input_tokens'] == 12
        assert group['resources']['dollar_cost']['value'] is None
        assert group['resources']['requested_models'] == ['fixed']
        assert group['resources']['returned_models'] == ['fixed-returned']
    config = json.loads((output/'config.json').read_text())
    assert config['fingerprints']['prompt_files']
    before = (output/'summary.json').read_bytes()
    assert regenerate_report(output) == summary
    assert (output/'summary.json').read_bytes() == before
    with pytest.raises(EvaluationError, match='output_exists'):
        await run_benchmark(dataset_path=path, output=output, approaches=['optimized'], split='dev', settings=settings(),
                            bootstrap_samples=10, verifiers={'optimized': verifier})
    assert (output/'summary.json').read_bytes() == before


@pytest.mark.parametrize('code', ['deadline_exceeded', 'invalid_model_output', 'not_configured'])
async def test_failure_denominators_and_unknown_usage(tmp_path, fixture, code):
    case, path = fixture
    verifier = MemoryVerifier(case, error=VerificationError(code))
    summary = await run_benchmark(dataset_path=path, output=tmp_path/'run', approaches=['minimal'],
                                  split='dev', track='oracle', settings=settings(), bootstrap_samples=10,
                                  verifiers={'minimal': verifier})
    group = summary['groups']['minimal/oracle']
    assert group['gold_claims'] == 2 and group['requested_cases'] == 1
    assert group['request_success']['value'] == 0
    assert group['resources']['total_usage'] is None
    assert group['resources']['requests_with_unknown_stats'] == 1
    if code == 'not_configured':
        assert group['status'] == 'NOT_RUN' and group['quality'] is None
    else:
        assert group['quality']['joint_evidence']['f1']['value'] == 0
    assert group['resources']['elapsed_ms']['count'] == 1


@pytest.mark.parametrize('kwargs,code', [({'rewrite': True}, 'oracle_identity_violation'),
                                        ({'invalid_quote': True}, 'invalid_model_output'),
                                        ({'slow': True}, 'deadline_exceeded')])
async def test_runner_rejects_identity_quote_and_bounds_protocol(tmp_path, fixture, kwargs, code):
    case, path = fixture
    verifier = MemoryVerifier(case, **kwargs)
    summary = await run_benchmark(dataset_path=path, output=tmp_path/'run', approaches=['optimized'],
                                  split='dev', track='oracle', settings=settings(operation_timeout=.02),
                                  bootstrap_samples=10, verifiers={'optimized': verifier})
    assert summary['groups']['optimized/oracle']['errors'] == {code: 1}
    record = json.loads((tmp_path/'run'/'records.jsonl').read_text())
    assert record['score']['counts']['gold'] == 2 and record['report'] is None
    if kwargs.get('rewrite'):
        assert record['rejected_report']['claims'][0]['claim_text'].endswith(' changed')


async def test_secret_exception_failure_logs_recovery_and_config_allowlist(tmp_path, fixture, capfd):
    case, path = fixture
    secret = 'SECRET_KEY_FAKE_94\nFORGED_RECORD'
    verifier = MemoryVerifier(case, error=RuntimeError(secret))
    configured = Settings(model='fixed', api_key=secret, base_url='https://invalid/'+secret, diagnostics=True)
    first = await run_benchmark(dataset_path=path, output=tmp_path/'failure', approaches=['minimal'],
                                split='dev', track='oracle', settings=configured, bootstrap_samples=10,
                                verifiers={'minimal': verifier})
    second = await run_benchmark(dataset_path=path, output=tmp_path/'recovery', approaches=['minimal'],
                                 split='dev', track='oracle', settings=configured, bootstrap_samples=10,
                                 verifiers={'minimal': MemoryVerifier(case)})
    captured = capfd.readouterr()
    assert secret not in captured.err and 'FORGED_RECORD' not in captured.err and not captured.out
    events = [json.loads(line) for line in captured.err.splitlines()]
    assert any(e.get('error_code') == 'internal_error' and e['stage'] == 'eval_case' for e in events)
    assert any(e['outcome'] == 'success' and e['stage'] == 'eval_run' for e in events)
    assert len({e['request_id'] for e in events}) == 4
    failure_record = json.loads((tmp_path/'failure'/'records.jsonl').read_text())
    assert any(e['request_id'] == failure_record['request_id'] and e.get('error_code') == 'internal_error'
               for e in events)
    assert first['completion']['status'] == 'COMPLETED_WITH_ERRORS'
    assert second['completion']['status'] == 'COMPLETE'
    assert secret not in (tmp_path/'failure'/'config.json').read_text()


async def test_incomplete_or_tampered_saved_runs_are_not_summarized(tmp_path, fixture):
    case, path = fixture
    output = tmp_path/'run'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev',
                        settings=settings(), bootstrap_samples=10, verifiers={'minimal': MemoryVerifier(case)})
    with (output/'records.jsonl').open('a') as stream:
        stream.write('{}\n')
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)
    (output/'completion.json').unlink()
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


def cli(*args, **kwargs):
    env = dict(os.environ, GROUNDING_PROVIDER='openai', GROUNDING_MODEL='', OPENAI_MODEL='', OPENAI_API_KEY='')
    return subprocess.run([sys.executable, '-m', 'grounding_eval', *map(str,args)],
                          env=env, stdout=subprocess.PIPE, stderr=kwargs.pop('stderr', subprocess.PIPE),
                          text=True, timeout=30, **kwargs)


def test_actual_cli_validate_failure_recovery_and_read_only_stderr(tmp_path, fixture):
    _, path = fixture
    good = cli('validate', '--dataset', path)
    assert good.returncode == 0 and json.loads(good.stdout)['status'] == 'VALID'
    assert all(json.loads(line)['stage'] == 'eval_validate' for line in good.stderr.splitlines())
    broken = tmp_path/'broken.jsonl'
    broken.write_text('{SECRET_DATA')
    bad = cli('validate', '--dataset', broken)
    assert bad.returncode == 2 and json.loads(bad.stdout)['error_code'] == 'dataset_invalid'
    assert 'SECRET_DATA' not in bad.stdout+bad.stderr
    with path.open('r') as nonwritable:
        recovered = cli('validate', '--dataset', path, stderr=nonwritable)
    assert recovered.returncode == 0 and json.loads(recovered.stdout) == json.loads(good.stdout)
    quiet = cli('validate', '--dataset', path, '--quiet')
    assert quiet.returncode == 0 and quiet.stderr == ''
    assert json.loads(quiet.stdout) == json.loads(good.stdout)


def test_actual_cli_missing_provider_is_not_run_not_heuristic_fallback(tmp_path, fixture):
    _, path = fixture
    output = tmp_path/'missing'
    result = cli('run', '--dataset', path, '--approaches', 'minimal,optimized', '--split', 'dev',
                 '--track', 'both', '--output', output, '--bootstrap-samples', '10')
    assert result.returncode == 2
    summary = json.loads(result.stdout)
    assert len(summary['groups']) == 4
    assert all(g['status'] == 'NOT_RUN' and g['quality'] is None for g in summary['groups'].values())
    assert all(g['errors'] == {'not_configured': 1} for g in summary['groups'].values())
    assert summary['paired_optimized_minus_minimal']['oracle']['status'] == 'NOT_RUN'
    before = (output/'summary.json').read_bytes()
    replay = cli('report', output)
    assert replay.returncode == 2 and json.loads(replay.stdout) == summary
    assert (output/'summary.json').read_bytes() == before


async def test_quota_stops_remaining_shared_model_jobs_without_invented_measurements(tmp_path, fixture):
    case, path = fixture
    clients = {name: MemoryVerifier(case, error=VerificationError('quota_exhausted'))
               for name in ('minimal', 'optimized')}
    output = tmp_path / 'quota'
    summary = await run_benchmark(dataset_path=path, output=output, approaches=list(clients),
                                  split='dev', settings=Settings(provider='codex', model='fixed', diagnostics=False),
                                  bootstrap_samples=10, verifiers=clients)
    records = [json.loads(line) for line in (output/'records.jsonl').read_text().splitlines()]
    assert sum(r['attempted'] for r in records) == 1
    assert len(records) == 4
    assert records[0]['status'] == 'ERROR' and records[0]['elapsed_ms'] >= 0
    assert all(r['status'] == 'NOT_RUN' and r['elapsed_ms'] is None and r['stats_known']
               and r['stats']['provider_calls'] == 0 and r['stats']['usage']['complete'] for r in records[1:])
    assert sum(r['score']['counts']['gold'] for r in records) == 8
    assert sum(len(client.inputs) for client in clients.values()) == 1
    assert summary['completion']['stopped_after_quota_exhausted']
    assert all(g['resources']['dollar_cost']['value'] is None for g in summary['groups'].values())
    assert all(g['status'] == 'NOT_RUN' for key,g in summary['paired_optimized_minus_minimal'].items())


async def test_saved_failure_usage_is_included_in_resources(tmp_path, fixture):
    case, path = fixture
    stats = RunStats(provider='codex', provider_calls=3, retries=1, repairs=1,
                     usage=TokenUsage(30, 5, complete=False))
    client = MemoryVerifier(case, error=VerificationError('upstream_timeout', stats=stats))
    summary = await run_benchmark(dataset_path=path, output=tmp_path/'failure_usage', approaches=['minimal'],
                                  split='dev', track='oracle', settings=settings(), bootstrap_samples=10,
                                  verifiers={'minimal': client})
    resource = summary['groups']['minimal/oracle']['resources']
    assert resource['known_usage']['input_tokens'] == 30
    assert resource['provider_calls_known'] == 3 and resource['retries_known'] == resource['repairs_known'] == 1
    assert resource['total_usage'] is None
    assert resource['elapsed_ms']['count'] == 1


async def test_persistence_failure_keeps_safe_category_and_next_run_recovers(tmp_path, fixture, monkeypatch, capfd):
    import grounding_eval.runner as module
    case, path = fixture
    original = module.write_json
    def unavailable(*args, **kwargs):
        raise OSError('SECRET_DISK_FAILURE')
    monkeypatch.setattr(module, 'write_json', unavailable)
    with pytest.raises(EvaluationError, match='persistence_failed'):
        await run_benchmark(dataset_path=path, output=tmp_path/'broken_storage', approaches=['minimal'],
                            split='dev', settings=Settings(diagnostics=True), bootstrap_samples=10,
                            verifiers={'minimal': MemoryVerifier(case)})
    emitted = capfd.readouterr().err
    assert 'SECRET_DISK_FAILURE' not in emitted
    assert any(json.loads(line).get('error_code') == 'persistence_failed' for line in emitted.splitlines())
    assert not (tmp_path/'broken_storage'/'completion.json').exists()
    monkeypatch.setattr(module, 'write_json', original)
    result = await run_benchmark(dataset_path=path, output=tmp_path/'after_storage', approaches=['minimal'],
                                 split='dev', settings=settings(), bootstrap_samples=10,
                                 verifiers={'minimal': MemoryVerifier(case)})
    assert result['completion']['status'] == 'COMPLETE'


async def test_public_report_rejects_promoted_not_run_completion(tmp_path, fixture):
    case, path = fixture
    output = tmp_path/'promoted-not-run'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal', 'optimized'],
                        split='dev', settings=settings(), bootstrap_samples=10,
                        verifiers={name: MemoryVerifier(case, error=VerificationError('not_configured'))
                                   for name in ('minimal', 'optimized')})
    before = (output/'summary.json').read_bytes()
    completion_path = output/'completion.json'
    completion = json.loads(completion_path.read_text())
    assert completion['status'] == 'COMPLETED_WITH_ERRORS'
    completion['status'] = 'COMPLETE'
    completion_path.write_text(json.dumps(completion))
    result = cli('report', output)
    assert result.returncode == 2
    assert json.loads(result.stdout) == {'error_code': 'run_artifact_invalid'}
    assert (output/'summary.json').read_bytes() == before


@pytest.mark.parametrize('field,value', [
    ('status', 'COMPLETE'),
    ('status', 'UNKNOWN'),
    ('record_count', True),
    ('record_count', 2),
    ('source_changed_during_run', 0),
    ('stopped_after_quota_exhausted', 0),
    ('stopped_after_quota_exhausted', True),
    ('cleanup_errors', None),
    ('cleanup_errors', [{'approach': 'unknown', 'error_code': 'internal_error'}]),
])
async def test_report_validates_completion_shape_and_consistency(tmp_path, fixture, field, value):
    case, path = fixture
    output = tmp_path/'completion-shape'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev', track='oracle',
                        settings=settings(), bootstrap_samples=10,
                        verifiers={'minimal': MemoryVerifier(case, error=VerificationError('not_configured'))})
    completion_path = output/'completion.json'
    completion = json.loads(completion_path.read_text())
    completion[field] = value
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


@pytest.mark.parametrize('field,value', [
    ('status', 'OK'),
    ('status', 'UNKNOWN'),
    ('sequence', True),
    ('family_id', 'other-family'),
    ('attempted', 1),
    ('error_code', None),
    ('elapsed_ms', None),
])
async def test_report_validates_saved_record_state_even_when_hash_matches(tmp_path, fixture, field, value):
    from grounding_eval.dataset import file_hash
    case, path = fixture
    output = tmp_path/'record-state'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev', track='oracle',
                        settings=settings(), bootstrap_samples=10,
                        verifiers={'minimal': MemoryVerifier(case, error=VerificationError('not_configured'))})
    records_path = output/'records.jsonl'
    record = json.loads(records_path.read_text())
    record[field] = value
    records_path.write_text(json.dumps(record)+'\n')
    completion_path = output/'completion.json'
    completion = json.loads(completion_path.read_text())
    completion['records_sha256'] = file_hash(records_path)
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


async def test_cleanup_failure_logs_phase_and_terminal_reason_without_exception_payload(tmp_path, fixture, capfd):
    case, path = fixture
    class BrokenCleanup(MemoryVerifier):
        async def aclose(self):
            raise RuntimeError('FAKE_CLEANUP_SECRET\nFORGED_CLEANUP')
    output = tmp_path/'cleanup-failure'
    summary = await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev',
                                  track='oracle', settings=Settings(diagnostics=True), bootstrap_samples=10,
                                  verifiers={'minimal': BrokenCleanup(case)})
    captured = capfd.readouterr()
    assert 'FAKE_CLEANUP_SECRET' not in captured.err and 'FORGED_CLEANUP' not in captured.err
    events = [json.loads(line) for line in captured.err.splitlines()]
    assert any(e['stage'] == 'eval_cleanup' and e['outcome'] == 'failure'
               and e['error_code'] == 'internal_error' and e['approach'] == 'minimal' for e in events)
    terminal = events[-1]
    assert terminal['stage'] == 'eval_run' and terminal['outcome'] == 'failure'
    assert terminal['error_code'] == 'cleanup_failed' and terminal['cleanup_failures'] == 1
    assert terminal['failed_requests'] == 0 and terminal['source_changed'] is False
    assert summary['completion']['status'] == 'COMPLETED_WITH_ERRORS'
    before = (output/'summary.json').read_bytes()
    assert regenerate_report(output) == summary
    assert (output/'summary.json').read_bytes() == before
    completion_path = output/'completion.json'
    completion = json.loads(completion_path.read_text())
    completion['status'] = 'COMPLETE'
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


@pytest.mark.parametrize('metadata', [
    {'source_changed_during_run': True},
    {'cleanup_errors': [{'approach': 'minimal', 'error_code': 'internal_error'}]},
])
async def test_report_rechecks_complete_against_valid_failure_metadata(tmp_path, fixture, metadata):
    case, path = fixture
    output = tmp_path/'metadata-failure'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev', track='oracle',
                        settings=settings(), bootstrap_samples=10, verifiers={'minimal': MemoryVerifier(case)})
    completion_path = output/'completion.json'
    completion = json.loads(completion_path.read_text())
    completion.update(metadata)
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)
    completion['status'] = 'COMPLETED_WITH_ERRORS'
    completion_path.write_text(json.dumps(completion))
    assert regenerate_report(output)['completion'] == completion


async def test_report_reuses_measurements_after_runtime_repairs_but_checks_scoring_fingerprints(tmp_path, fixture, monkeypatch):
    import copy

    import grounding_eval.runner as module
    case, path = fixture
    output = tmp_path/'fingerprints'
    summary = await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev', track='oracle',
                                  settings=settings(), bootstrap_samples=10, verifiers={'minimal': MemoryVerifier(case)})
    current = copy.deepcopy(module.fingerprints())
    current['files']['grounding_eval/runner.py'] = '0'*64
    current['files']['grounding_eval/diagnostics.py'] = '0'*64
    monkeypatch.setattr(module, 'fingerprints', lambda: current)
    before = (output/'summary.json').read_bytes()
    assert regenerate_report(output) == summary
    assert (output/'summary.json').read_bytes() == before
    current['files']['grounding_eval/scoring.py'] = '0'*64
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)
    assert (output/'summary.json').read_bytes() == before
