import copy
import json
import os
import subprocess
import sys

import pytest

from grounding.config import Settings
from grounding.contracts import RunStats, VerificationError, VerificationReport, VerificationRun
from grounding_eval.dataset import DatasetError, file_hash, load_dataset
from grounding_eval.runner import EvaluationError, regenerate_report, run_benchmark


class CountingVerifier:
    def __init__(self, case, *, calls=1, fail_unknown=False):
        self.case = case
        self.calls = calls
        self.fail_unknown = fail_unknown
        self.inputs = []

    async def verify(self, request):
        self.inputs.append(request.model_dump())
        return self.result()

    async def verify_claims(self, context_passages, claims):
        self.inputs.append({'context_passages': context_passages, 'claims': claims})
        return self.result()

    def result(self):
        if self.fail_unknown:
            raise VerificationError('upstream_timeout')
        claims = [
            {'claim_text': gold.claim_text, 'verdict': gold.verdict, 'reasoning': 'Offline fixture.',
             'citations': [c.model_dump() for c in gold.evidence_sets[0]] if gold.evidence_sets else []}
            for gold in self.case.gold_claims
        ]
        return VerificationRun(VerificationReport.model_validate({'claims': claims}),
                               RunStats(provider='codex', requested_model='offline',
                                        provider_calls=self.calls))

    async def aclose(self):
        pass


async def test_selected_real_population_keeps_dependencies_for_offline_replay(v2_fixture, tmp_path):
    path, _, _ = v2_fixture
    case = load_dataset(path)[0]
    client = CountingVerifier(case)
    output = tmp_path / 'run'
    summary = await run_benchmark(
        dataset_path=path, output=output, approaches=['minimal'], split='dev', track='end-to-end',
        settings=Settings(diagnostics=False), bootstrap_samples=5,
        case_ids=[case.id], max_total_provider_attempts=6, verifiers={'minimal': client})
    assert set(client.inputs[0]) == {'context_passages', 'generated_answer'}
    config = json.loads((output / 'config.json').read_text())
    assert config['schema_version'] == '2' and config['dataset_version'] == 'offline-1'
    assert config['scorer_version'] == '2'
    assert config['execution']['jobs'][0]['case_id'] == case.id
    assert len(load_dataset(output / 'cases.jsonl')[0].gold_claims) == 3
    (path.parent / 'source.txt').unlink()
    path.unlink()
    assert regenerate_report(output) == summary
    snapshot = output / config['dataset_snapshot']['path']
    assert snapshot.exists()
    (snapshot.parent / 'source.txt').write_text('SECRET_CHANGED')
    before = (output / 'summary.json').read_bytes()
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)
    assert (output / 'summary.json').read_bytes() == before


@pytest.mark.parametrize('unknown', [False, True])
async def test_budget_reserves_each_job_and_retains_all_omitted_denominators(
        v2_fixture, tmp_path, unknown):
    path, _, _ = v2_fixture
    case = load_dataset(path)[0]
    clients = {name: CountingVerifier(case, fail_unknown=unknown and name != 'heuristic')
               for name in ('minimal', 'optimized', 'heuristic')}
    output = tmp_path / 'budget'
    summary = await run_benchmark(
        dataset_path=path, output=output, approaches=list(clients), split='dev', track='both',
        settings=Settings(diagnostics=False, max_provider_attempts=3), bootstrap_samples=5,
        max_total_provider_attempts=4, verifiers=clients)
    records = [json.loads(line) for line in (output / 'records.jsonl').read_text().splitlines()]
    model = [r for r in records if r['approach'] != 'heuristic']
    assert len(model) == 4 and sum(r['attempted'] for r in model) == (1 if unknown else 2)
    assert sum(r['provider_attempts_charged'] for r in records) == (3 if unknown else 2)
    stopped = [r for r in model if not r['attempted']]
    assert stopped and all(r['status'] == 'NOT_RUN' and r['error_code'] == 'attempt_budget_exhausted'
                           and r['started_at'] is None and r['elapsed_ms'] is None for r in stopped)
    assert all(r['score']['counts']['gold'] == 3 for r in records)
    assert len(clients['heuristic'].inputs) == 2
    assert summary['completion']['stopped_after_attempt_budget_exhausted']
    assert summary['completion']['status'] == 'COMPLETED_WITH_ERRORS'
    assert all(group['failure_inclusive_quality']['counts']['gold'] == 3
               for group in summary['groups'].values())
    assert regenerate_report(output) == summary


@pytest.mark.parametrize('ids', [[], ['unknown'], ['real-queue', 'real-queue'], [False], 'real-queue'])
async def test_case_selection_rejects_missing_duplicate_and_untyped_ids(v2_fixture, tmp_path, ids):
    path, _, _ = v2_fixture
    with pytest.raises((EvaluationError, DatasetError)):
        await run_benchmark(dataset_path=path, output=tmp_path / 'bad', approaches=['heuristic'],
                            split='dev', case_ids=ids, bootstrap_samples=5,
                            settings=Settings(diagnostics=False))
    assert not (tmp_path / 'bad').exists()


async def test_actual_model_runs_require_explicit_total_attempt_budget(v2_fixture, tmp_path):
    path, _, _ = v2_fixture
    with pytest.raises(EvaluationError, match='invalid_arguments'):
        await run_benchmark(dataset_path=path, output=tmp_path / 'no-budget', approaches=['minimal'],
                            split='dev', settings=Settings(diagnostics=False), bootstrap_samples=5)


@pytest.mark.parametrize('field,value', [('provider_attempts_charged', 0), ('started_at', None)])
async def test_replay_rejects_broken_budget_or_start_even_with_matching_hash(
        v2_fixture, tmp_path, field, value):
    path, _, _ = v2_fixture
    case = load_dataset(path)[0]
    output = tmp_path / 'run'
    await run_benchmark(dataset_path=path, output=output, approaches=['minimal'], split='dev',
                        track='oracle', max_total_provider_attempts=6, bootstrap_samples=5,
                        settings=Settings(diagnostics=False),
                        verifiers={'minimal': CountingVerifier(case)})
    record_path = output / 'records.jsonl'
    record = json.loads(record_path.read_text())
    record[field] = value
    record_path.write_text(json.dumps(record) + '\n')
    completion_path = output / 'completion.json'
    completion = json.loads(completion_path.read_text())
    completion['records_sha256'] = file_hash(record_path)
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


async def test_new_scoring_dependencies_remain_in_replay_hash_guard(v2_fixture, tmp_path, monkeypatch):
    import grounding_eval.runner as module

    path, _, _ = v2_fixture
    output = tmp_path / 'run'
    await run_benchmark(dataset_path=path, output=output, approaches=['heuristic'], split='dev',
                        track='oracle', bootstrap_samples=5, settings=Settings(diagnostics=False))
    for name in ('grounding_eval/provenance.py', 'grounding_eval/repeated.py'):
        current = copy.deepcopy(module.fingerprints())
        current['files'][name] = '0' * 64
        with monkeypatch.context() as patch:
            patch.setattr(module, 'fingerprints', lambda: current)
            with pytest.raises(EvaluationError, match='run_artifact_invalid'):
                regenerate_report(output)


@pytest.mark.parametrize('defect', ['selection', 'split', 'seed', 'score_bool', 'duplicate_json'])
async def test_replay_rejects_population_metadata_damage(v2_fixture, tmp_path, defect):
    path, _, _ = v2_fixture
    output = tmp_path / 'run'
    await run_benchmark(dataset_path=path, output=output, approaches=['heuristic'], split='dev',
                        track='both', bootstrap_samples=5, settings=Settings(diagnostics=False))
    config_path = output / 'config.json'
    records_path = output / 'records.jsonl'
    config = json.loads(config_path.read_text())
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    if defect == 'selection':
        config['selection'] = {'kind': 'case_ids', 'requested_case_ids': ['missing']}
    elif defect == 'split':
        config['split'] = 'test'
    elif defect == 'seed':
        config['seed'] = True
    elif defect == 'score_bool':
        records[0]['score']['counts']['requested'] = True
    if defect == 'duplicate_json':
        record_text = json.dumps(records[0])
        records_path.write_text('{"sequence":99,' + record_text[1:] + '\n'
                                + json.dumps(records[1]) + '\n')
    else:
        records_path.write_text(''.join(json.dumps(record) + '\n' for record in records))
    config_path.write_text(json.dumps(config))
    completion_path = output / 'completion.json'
    completion = json.loads(completion_path.read_text())
    completion.update(config_sha256=file_hash(config_path), records_sha256=file_hash(records_path))
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(EvaluationError, match='run_artifact_invalid'):
        regenerate_report(output)


@pytest.mark.parametrize('selection', [None, 'real-queue', {'case_id': 'real-queue'}, [False], []])
def test_public_cli_requires_string_list_selection(v2_fixture, tmp_path, selection):
    path, _, _ = v2_fixture
    selected = tmp_path / 'selected.json'
    selected.write_text(json.dumps(selection))
    result = subprocess.run(
        [sys.executable, '-m', 'grounding_eval', 'run', '--dataset', str(path), '--approaches',
         'heuristic', '--split', 'dev', '--case-ids-file', str(selected), '--output', str(tmp_path / 'bad'),
         '--bootstrap-samples', '3'], capture_output=True, text=True, timeout=20)
    assert result.returncode == 2 and json.loads(result.stdout)['error_code'] == 'invalid_arguments'
    assert not (tmp_path / 'bad').exists()


def test_public_cli_zero_budget_preserves_model_population_and_runs_heuristic(v2_fixture, tmp_path):
    path, raw, _ = v2_fixture
    selected = tmp_path / 'selected.json'
    selected.write_text(json.dumps([raw['id']]))
    output = tmp_path / 'zero-budget'
    env = dict(os.environ, GROUNDING_PROVIDER='openai', GROUNDING_MODEL='', OPENAI_MODEL='',
               OPENAI_API_KEY='')
    result = subprocess.run(
        [sys.executable, '-m', 'grounding_eval', 'run', '--dataset', str(path), '--approaches',
         'minimal,optimized,heuristic', '--split', 'dev', '--case-ids-file', str(selected),
         '--max-total-provider-attempts', '0', '--output', str(output), '--bootstrap-samples', '3'],
        env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    summary = json.loads(result.stdout)
    assert summary['completion']['record_count'] == 6
    assert summary['completion']['provider_attempts_charged'] == 0
    assert summary['groups']['heuristic/oracle']['status'] == 'COMPLETE'
    assert summary['groups']['optimized/oracle']['errors'] == {'attempt_budget_exhausted': 1}
    assert summary['groups']['optimized/oracle']['failure_inclusive_quality']['counts']['gold'] == 3
