"""Replay the auxiliary aggregate from a holder's private saved run, offline."""
from __future__ import annotations

import argparse
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
# The offline guard must precede imports of evaluator/provider modules.
import grounding.verifiers  # noqa: E402
from grounding.codex_auth import CredentialStore  # noqa: E402
from grounding.config import Settings  # noqa: E402
from grounding_eval.reporting import resources  # noqa: E402
from grounding_eval.runner import fingerprints, read_saved_run, regenerate_report  # noqa: E402


def deny(*args, **kwargs):
    raise RuntimeError('offline_inference_or_credentials_guard')


Settings.from_env = deny
CredentialStore.load = deny
grounding.verifiers.build_verifier = deny
FOLDER = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def aggregate_projection(summary, records, plan):
    group_fields = ('status', 'requested_cases', 'statuses', 'gold_claims', 'request_success',
                    'errors', 'failure_inclusive_quality', 'uncertainty', 'resources')
    return {
        'scope': 'Nine pre-result-selected natural Summary responses; purposive auxiliary only.',
        'source_commit': plan['source_commit'],
        'code_sha256': plan['source_fingerprints']['code_sha256'],
        'dataset_sha256': plan['dataset_sha256'], 'manifest_sha256': plan['manifest_sha256'],
        'annotation_version': plan['annotation_version'],
        'cases': 9, 'gold_claims_per_method_track': 125, 'independent_source_families': 9,
        'case_ids': plan['case_ids'],
        'pre_result_exclusions': plan['pre_result_exclusions'],
        'groups': {name: {field: group[field] for field in group_fields}
                   for name, group in summary['groups'].items()},
        'paired_optimized_minus_minimal': summary['paired_optimized_minus_minimal'],
        'all_requested_job_resources': resources(records, None),
        'all_ERROR_and_NOT_RUN_retained': True,
        'strict_metrics_are_not_semantic_entailment': True,
        'no_natural_response_semantic_audit_claimed': True,
        'human_review': 'not_performed',
        'private_materials_published': False,
        'limitations': plan['limitations'] + summary['limitations'],
    }


def replay(folder, receipt=None):
    plan = read(FOLDER / 'experiment-plan.json')
    assert fingerprints() == plan['source_fingerprints'], 'exact_archived_source_required'
    before = hashes(folder)
    if receipt is not None:
        assert hashlib.sha256((FOLDER / 'experiment-plan.json').read_bytes()).hexdigest() == receipt['source_freeze_sha256']
        assert before == receipt['private_run_artifact_hashes'], 'private_saved_run_changed'
    config, records, _, completion = read_saved_run(folder)
    assert config['fingerprints'] == plan['source_fingerprints']
    assert config['settings'] == plan['settings']
    assert config['dataset_sha256'] == plan['dataset_sha256']
    assert config['case_ids'] == plan['case_ids'] and len(records) == 54
    assert [{k: row[k] for k in ('sequence', 'case_id', 'approach', 'track')}
            for row in records] == plan['job_order']
    summary = regenerate_report(folder)
    assert hashes(folder) == before, 'replay_changed_private_files'
    result = aggregate_projection(summary, records, plan)
    return result, before, completion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-run', type=Path, required=True)
    args = parser.parse_args()
    receipt = read(FOLDER / 'execution-receipt.json')
    result, before, _ = replay(args.private_run, receipt)
    assert result == read(FOLDER / 'aggregate-results.json'), 'aggregate_changed'
    print(json.dumps({'status': 'IDENTICAL_PRIVATE_RUN_AND_PUBLIC_AGGREGATE',
                      'byte_identical_private_files': len(before), 'new_inference_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
