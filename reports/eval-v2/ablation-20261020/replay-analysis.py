"""Read-only C01 paired analysis replay; no inference, credentials, or network."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('offline_network_guard')
    if event == 'open' and args and isinstance(args[0], str):
        if Path(args[0]).name in {'.env', '.env.local'}:
            raise RuntimeError('offline_env_guard')


sys.addaudithook(guard)
sys.dont_write_bytecode = True
# The network/environment guard must precede evaluator imports.
import grounding.verifiers  # noqa: E402
from grounding.codex_auth import CredentialStore  # noqa: E402
from grounding.config import Settings  # noqa: E402
from grounding_eval.dataset import load_dataset  # noqa: E402
from grounding_eval.reporting import resources  # noqa: E402
from grounding_eval.runner import fingerprints  # noqa: E402
from grounding_eval.scoring import aggregate, primary_values, score_case  # noqa: E402
from grounding_eval.uncertainty import bootstrap  # noqa: E402


def deny(*args, **kwargs):
    raise RuntimeError('offline_inference_or_credentials_guard')


Settings.from_env = deny
CredentialStore.load = deny
grounding.verifiers.build_verifier = deny
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def read(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


if __name__ == '__main__':
    plan = read(ROOT / 'experiment-plan.json')
    analysis = read(ROOT / 'analysis.json')
    mapping = read(ROOT / 'analysis-row-map.json')
    assert fingerprints()['code_sha256'] in {
        value['code_sha256'] for value in plan['source_fingerprints'].values()}
    cases = {c.id: c for c in load_dataset(
        REPO / 'reports/eval-v2/completion-dev-20261020/matrix/cases.jsonl')}
    rows = {name: [] for name in ('control1', 'candidate1', 'control2', 'candidate2')}
    scores = {name: [] for name in rows}
    seen = set()
    for item in mapping['rows']:
        identity = (item['condition'], item['observation'], item['case_id'])
        assert identity not in seen
        seen.add(identity)
        raw = (REPO / item['source']).read_bytes()
        assert digest(raw) == item['source_records_sha256']
        line = raw.splitlines(keepends=True)[item['source_line_index']]
        assert digest(line) == item['source_row_sha256']
        row = json.loads(line)
        assert row['sequence'] == item['source_sequence']
        assert row['request_id'] == item['source_request_id']
        assert row['case_id'] == item['case_id'] and row['status'] == item['status']
        assert row['approach'] == 'minimal' and row['track'] == 'end-to-end'
        assert row['attempted'] is True and row['status'] in {'OK', 'ERROR'}
        score = score_case(cases[row['case_id']],
                           row['report']['claims'] if row['report'] else [],
                           track='end-to-end', error=row['error_code'])
        assert score == row['score']
        name = item['condition'] + str(item['observation'])
        rows[name].append(row)
        scores[name].append({**score, 'repetition': item['observation']})
    assert len(seen) == 48 and all(len(group) == 12 for group in rows.values())
    assert sum(r['status'] == 'ERROR' for r in rows['control1']) == 1
    candidate = scores['candidate1'] + scores['candidate2']
    control = scores['control1'] + scores['control2']
    assert aggregate(candidate) == analysis['candidate_failure_inclusive_quality']
    assert aggregate(control) == analysis['control_failure_inclusive_quality']
    paired = bootstrap(candidate, paired_scores=control, seed=plan['seed'],
                       samples=plan['bootstrap_samples'])
    assert paired == analysis['paired_candidate_minus_control_family_bootstrap']
    for repetition in (1, 2):
        a, b = 'candidate' + str(repetition), 'control' + str(repetition)
        observed = analysis['per_observation'][str(repetition)]
        assert aggregate(scores[a]) == observed['candidate']
        assert aggregate(scores[b]) == observed['control']
        av, bv = primary_values(scores[a]), primary_values(scores[b])
        assert {k: av[k] - bv[k] if av[k] is not None and bv[k] is not None else None
                for k in av} == observed['candidate_minus_control']
        assert resources(rows[a], None) == observed['candidate_resources']
        assert resources(rows[b], None) == observed['control_resources']
    assert resources(rows['candidate1'] + rows['candidate2'], None) == analysis['candidate_resources']
    assert resources(rows['control1'] + rows['control2'], None) == analysis['control_resources']
    print(json.dumps({'status': 'IDENTICAL_PAIRED_ANALYSIS', 'mapped_rows': 48,
                      'independent_source_families': 12, 'observations_per_condition': 24,
                      'inference_calls': 0, 'credential_reads': 0, 'network_calls': 0}))
