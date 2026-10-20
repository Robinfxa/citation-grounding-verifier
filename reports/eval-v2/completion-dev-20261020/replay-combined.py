"""Read-only replay of the explicitly mapped analytical population; never inference."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def offline_guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('offline_network_guard')
    if event == 'open' and args and isinstance(args[0], str):
        if Path(args[0]).name in {'.env', '.env.local'}:
            raise RuntimeError('offline_env_guard')


sys.addaudithook(offline_guard)
# The network/environment guard must precede evaluator imports.
from grounding.config import Settings  # noqa: E402
from grounding_eval.dataset import load_dataset  # noqa: E402
from grounding_eval.reporting import build_summary  # noqa: E402
from grounding_eval.runner import fingerprints, json_text  # noqa: E402


def denied(*args, **kwargs):
    raise RuntimeError('offline_settings_guard')


Settings.from_env = denied
ROOT = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reconstruct():
    manifest = json.loads((ROOT / 'combined-analysis/source-row-map.json').read_text())
    assert fingerprints()['code_sha256'] == manifest['source_code_sha256']
    original_bytes = (ROOT / 'matrix/records.jsonl').read_bytes()
    original_lines = original_bytes.splitlines(keepends=True)
    assert digest(original_bytes) == manifest['original_records_sha256']
    config = json.loads((ROOT / 'matrix/config.json').read_text())
    cases = load_dataset(ROOT / 'matrix/cases.jsonl')
    rows, raw_rows, seen, sources = [], [], set(), {}
    for item in manifest['rows']:
        sequence = item['original_sequence']
        original = json.loads(original_lines[sequence])
        identity = tuple(original[k] for k in ('case_id','approach','track'))
        assert identity not in seen
        seen.add(identity)
        run = item['source_run']
        assert run in {'matrix','recovery-01-minimal-oracle','recovery-02-minimal-e2e',
                       'recovery-03-optimized-oracle','recovery-04-optimized-e2e'}
        if run not in sources:
            raw = (ROOT / run / 'records.jsonl').read_bytes()
            source_config = json.loads((ROOT / run / 'config.json').read_text())
            assert source_config['fingerprints'] == config['fingerprints']
            assert source_config['settings'] == config['settings']
            assert source_config['seed'] == config['seed']
            assert source_config['dataset_sha256'] == config['dataset_sha256']
            assert source_config['split'] == 'dev' and source_config['stop_on_model_error'] is True
            assert source_config['bootstrap_samples'] == config['bootstrap_samples']
            sources[run] = (raw, raw.splitlines(keepends=True))
        raw, lines = sources[run]
        assert digest(raw) == item['source_records_sha256']
        assert digest((ROOT / run / 'config.json').read_bytes()) == item['source_config_sha256']
        line = lines[item['source_line_index']]
        assert digest(line) == item['source_row_sha256']
        selected = json.loads(line)
        assert tuple(selected[k] for k in ('case_id','approach','track')) == identity
        assert selected['sequence'] == item['source_sequence']
        if original['status'] in {'OK','ERROR'}:
            assert run == 'matrix' and line == original_lines[sequence]
        else:
            assert original['status'] == 'NOT_RUN' and original['attempted'] is False
        assert selected['attempted'] is True and selected['status'] in {'OK','ERROR'}
        rows.append(selected)
        raw_rows.append(line)
    assert len(rows) == len(original_lines) == len(seen) == 72
    assert manifest['rows'] == sorted(manifest['rows'],key=lambda r:r['original_sequence'])
    analysis_config = {**config,'measurement_kind':'actual_verifier_rows_analytical_combination'}
    summary = build_summary(analysis_config, rows, cases)
    summary['analysis'] = {
        'kind':'failure_inclusive_immutable_row_combination_not_a_single_successful_run',
        'source_runs':sorted(sources),'requested_jobs':len(rows),
        'statuses':dict(sorted(Counter(r['status'] for r in rows).items())),
        'gold_claims_per_method_track':126,'independent_development_cases':12,
        'original_error_retained':True,'original_not_run_rows_replaced_only':True,
        'temporal_order':'Four approach/track blocks followed the initial matrix stop; provider drift remains possible.',
        'original_matrix_cli_exit_code':2,'checks_excluded_from_comparison':True,
    }
    return b''.join(raw_rows), json_text(summary).encode()


if __name__ == '__main__':
    raw, summary = reconstruct()
    assert (ROOT / 'combined-analysis/records.jsonl').read_bytes() == raw
    assert (ROOT / 'combined-analysis/summary.json').read_bytes() == summary
    print(json.dumps({'status':'BYTE_IDENTICAL_COMBINED_ANALYSIS','mapped_jobs':72,
                      'network_calls':0,'inference_calls':0,'credential_reads':0}))
