"""Replay saved final reports with the exact archived source and no inference."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise RuntimeError('offline_network_guard')
    if event == 'open' and args and isinstance(args[0], str):
        if Path(args[0]).name in {'.env', '.env.local'}:
            raise RuntimeError('offline_env_guard')


sys.addaudithook(guard)
sys.dont_write_bytecode = True
# The guard deliberately precedes all evaluator imports.
import grounding.verifiers  # noqa: E402
from grounding.codex_auth import CredentialStore  # noqa: E402
from grounding.config import Settings  # noqa: E402
from grounding_eval import audit  # noqa: E402
from grounding_eval.dataset import GoldClaim  # noqa: E402
from grounding_eval.repeated import analyze_repeated, read_repeated_run  # noqa: E402
from grounding_eval.runner import fingerprints  # noqa: E402
from grounding_eval.scoring import aggregate, evidence_covered, prf  # noqa: E402


def deny(*args, **kwargs):
    raise RuntimeError('offline_inference_or_credentials_guard')


Settings.from_env = deny
CredentialStore.load = deny
grounding.verifiers.build_verifier = deny
FOLDER = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def verify_audit_population(audit_root, records, cases, plan):
    """Bind both anonymous inventories to the fixed selections and actual raw run."""
    preparation = read(FOLDER / 'audit-preparation.json')
    policy_hash = plan['semantic_audit_policy']['sha256']
    assert digest(FOLDER.parent / Path(plan['semantic_audit_policy']['file']).name) == policy_hash
    module_hash = digest(Path(audit.__file__))
    assert module_hash == plan['source_fingerprints']['files']['grounding_eval/audit.py']
    all_ids = read(FOLDER / 'audit-case-ids.json')
    for name in ('audit-case-ids.json', 'audit-batch-01-case-ids.json', 'audit-batch-02-case-ids.json'):
        assert digest(FOLDER / name) == plan['input_hashes'][f'reports/eval-v2/{FOLDER.name}/{name}']
    selections = [read(FOLDER / f'audit-batch-{i:02d}-case-ids.json') for i in (1, 2)]
    assert all(len(ids) == len(set(ids)) == 12 for ids in selections)
    assert not set(selections[0]) & set(selections[1])
    assert sorted(selections[0] + selections[1]) == sorted(all_ids)
    assert len(all_ids) == len(set(all_ids)) == plan['fixed_selections']['audit_cases']
    indexed = {(row['case_id'], row['approach'], row['track']): row for row in records}
    assert len(indexed) == len(records)
    run_hashes = {name: digest(FOLDER / 'full-test' / name) for name in
                  ('config.json', 'cases.jsonl', 'records.jsonl', 'completion.json')}
    prepared = {entry['batch']: entry for entry in preparation['batches']}
    assert len(preparation['batches']) == 2 and set(prepared) == {1, 2}
    memberships, families = [], set()
    batches = []
    for number, selected in enumerate(selections, 1):
        folder = audit_root / f'batch-{number:02d}'
        packet, key = read(folder / 'alignment-input.json'), read(folder / 'key.json')
        selection_hash = digest(FOLDER / f'audit-batch-{number:02d}-case-ids.json')
        assert packet['audit_version'] == audit.AUDIT_VERSION
        assert packet['policy_sha256'] == key['policy_sha256'] == policy_hash
        assert packet['selection_sha256'] == selection_hash == prepared[number]['selection_sha256']
        assert digest(folder / 'alignment-input.json') == prepared[number]['alignment_input_sha256']
        assert digest(folder / 'key.json') == prepared[number]['key_sha256']
        assert key['module_sha256'] == module_hash and key['run_files_sha256'] == run_hashes
        assert set(packet) == {'audit_version', 'policy_sha256', 'selection_sha256', 'items'}
        item_ids = [item['item_id'] for item in packet['items']]
        assert len(item_ids) == len(set(item_ids)) == len(selected) * len(plan['approaches'])
        assert set(item_ids) == set(key['items'])
        actual_members = [(entry['case']['id'], entry['record']['approach']) for entry in key['items'].values()]
        expected = [(case_id, approach) for case_id in selected for approach in plan['approaches']]
        assert Counter(actual_members) == Counter(expected), 'audit_case_method_population_changed'
        for item in packet['items']:
            entry = key['items'][item['item_id']]
            row, case = entry['record'], entry['case']
            assert case == cases[case['id']], 'audit_case_differs_from_original'
            assert row['track'] == 'end-to-end'
            assert row == indexed[case['id'], row['approach'], 'end-to-end'], 'audit_record_differs_from_original'
            predictions = row['report']['claims'] if row['report'] else []
            assert item == {'item_id': item['item_id'], 'answer': case['generated_answer'],
                            'gold_claims': [{'id': gold['id'], 'text': gold['claim_text']} for gold in case['gold_claims']],
                            'predictions': [{'index': i, 'text': p['claim_text']} for i, p in enumerate(predictions)]}
        batch_families = {cases[case_id]['family_id'] for case_id in selected}
        assert prepared[number]['independent_source_families'] == len(batch_families)
        memberships.extend(actual_members)
        families.update(batch_families)
        batches.append({'number': number, 'folder': folder, 'key': key, 'packet': packet,
                        'case_ids': selected, 'families': batch_families})
    assert Counter(memberships) == Counter((case_id, approach) for case_id in all_ids for approach in plan['approaches'])
    assert len(memberships) == preparation['total_anonymous_items'] == 72
    assert len(families) == preparation['independent_source_families'] == plan['fixed_selections']['audit_source_families']
    assert preparation['source_records_sha256'] == run_hashes['records.jsonl']
    assert preparation['source_config_sha256'] == run_hashes['config.json']
    assert preparation['source_completion_sha256'] == run_hashes['completion.json']
    assert preparation['audit_module_sha256'] == module_hash and preparation['policy_sha256'] == policy_hash
    return batches


def replay_audit(first_run, plan):
    result = read(FOLDER / 'semantic-audit-analysis.json')
    cases = {case['id']: case for case in map(json.loads, (FOLDER / 'full-test/cases.jsonl').read_text().splitlines())}
    indexed = {(row['case_id'], row['approach'], row['track']): row for row in first_run['records']}
    verified_batches = verify_audit_population(FOLDER / 'semantic-audit', first_run['records'], cases, plan)
    summaries = []
    judgment_counts = {approach: {field: Counter() for field in ('label', 'evidence', 'quote_economy')}
                       for approach in plan['approaches']}
    for verified in verified_batches:
        folder = verified['folder']
        summary = audit.summarize(folder, folder / 'evidence-review.json')
        assert summary == read(folder / 'summary.json'), 'audit_batch_summary_changed'
        assert summary['policy_sha256'] == plan['semantic_audit_policy']['sha256']
        key = verified['key']
        review = read(folder / 'evidence-review.json')
        for item in review['items']:
            approach = key['items'][item['item_id']]['record']['approach']
            for judgment in item['judgments']:
                for field, counts_by_value in judgment_counts[approach].items():
                    counts_by_value.update([judgment[field]])
        summaries.append(summary)
    ids = read(FOLDER / 'audit-case-ids.json')
    assert result['cases'] == len(ids)
    assert result['anonymous_case_method_items'] == sum(len(batch['packet']['items']) for batch in verified_batches)
    assert result['case_selection_sha256'] == digest(FOLDER / 'audit-case-ids.json')
    assert result['source_records_sha256'] == digest(FOLDER / 'full-test/records.jsonl')
    assert result['policy_sha256'] == plan['semantic_audit_policy']['sha256']
    groups = {}
    for approach in plan['approaches']:
        counts = Counter()
        for summary in summaries:
            counts.update(summary['groups'][approach]['counts'])
        selected = [indexed[case_id, approach, 'end-to-end']['score'] for case_id in ids]
        source_families = len({cases[case_id]['family_id'] for case_id in ids})
        groups[approach] = {
            'counts': dict(counts), 'source_families': source_families, 'case_ids': sorted(ids),
            'semantic_decomposition': prf(counts['equivalent'], counts['predicted'], counts['gold']),
            'joint_label': prf(counts['label_correct'], counts['predicted'], counts['gold']),
            'joint_evidence': prf(counts['evidence_correct'], counts['predicted'], counts['gold']),
            'same_subset_strict_failure_inclusive_quality': aggregate(selected),
            'equivalent_pair_judgment_counts': {field: dict(values)
                                                for field, values in judgment_counts[approach].items()},
        }
    assert groups == result['groups'], 'pooled_audit_changed'
    assert result['independent_source_families'] == len({cases[case_id]['family_id'] for case_id in ids})
    if (FOLDER / 'semantic-audit-adjudication.json').exists():
        replay_audit_adjudication(groups)
    print(json.dumps({'audit_batches': len(verified_batches), 'fixed_cases': len(ids), 'status': 'IDENTICAL',
                      'new_inference_calls': 0}), flush=True)


def replay_audit_adjudication(groups):
    """Rebuild the two-vote sensitivity, without claiming to rejudge semantics."""
    note = read(FOLDER / 'semantic-audit-adjudication.json')
    result = read(FOLDER / 'semantic-audit-correction-sensitivity.json')
    original_hash = digest(FOLDER / 'semantic-audit-analysis.json')
    assert note['original_analysis_sha256'] == result['original_analysis_sha256'] == original_hash
    assert result['adjudication_sha256'] == digest(FOLDER / 'semantic-audit-adjudication.json')
    changes = note['confirmed_review_corrections']
    assert len(changes) == len({(e['batch'], e['item_id'], e['gold_id'], e['prediction_index']) for e in changes}) == 2
    additions = Counter()
    for entry in changes:
        folder = FOLDER / 'semantic-audit' / f"batch-{entry['batch']:02d}"
        assert digest(folder / 'evidence-review.json') == entry['original_evidence_review_sha256']
        assert digest(folder / 'alignment-lock.json') == entry['alignment_lock_sha256']
        assert digest(folder / 'evidence-input.json') == entry['evidence_input_sha256']
        key = read(folder / 'key.json')['items'][entry['item_id']]
        item = next(i for i in read(folder / 'evidence-review.json')['items'] if i['item_id'] == entry['item_id'])
        vote = next(j for j in item['judgments'] if j['gold_id'] == entry['gold_id']
                    and j['prediction_index'] == entry['prediction_index'])
        assert vote == entry['original_judgment']
        assert vote['label'] == 'correct' and vote['evidence'] == 'insufficient'
        assert entry['confirmed_evidence_value'] == 'sufficient'
        assert key['record']['approach'] == entry['approach'] == 'optimized'
        assert key['case']['id'] == entry['case_id']
        assert key['record']['sequence'] == entry['source_record_sequence']
        assert key['record']['report']['claims'][entry['prediction_index']]['citations'] == entry['prediction_citations']
        additions.update([entry['approach']])
    expected = {}
    for name, group in groups.items():
        counts = group['counts'].copy()
        counts['evidence_correct'] += additions[name]
        judgments = {field: values.copy() for field, values in group['equivalent_pair_judgment_counts'].items()}
        if additions[name]:
            judgments['evidence']['insufficient'] -= additions[name]
            judgments['evidence']['sufficient'] += additions[name]
        expected[name] = {
            'counts': counts, 'original_joint_evidence': group['joint_evidence'],
            'sensitivity_joint_evidence': prf(counts['evidence_correct'], counts['predicted'], counts['gold']),
            'equivalent_pair_judgment_counts': judgments,
            'applied_confirmed_corrections': additions[name],
        }
    assert expected == result['groups'], 'two_vote_sensitivity_changed'
    pending = note['unresolved_proxy_issue']
    folder = FOLDER / 'semantic-audit' / f"batch-{pending['batch']:02d}"
    assert digest(folder / 'evidence-review.json') == pending['original_evidence_review_sha256']
    key = read(folder / 'key.json')['items'][pending['item_id']]
    assert key['case']['id'] == pending['case_id']
    assert key['record']['approach'] == pending['approach']
    assert key['record']['sequence'] == pending['source_record_sequence']
    item = next(i for i in read(folder / 'evidence-review.json')['items'] if i['item_id'] == pending['item_id'])
    assert pending['original_judgment'] == next(j for j in item['judgments'] if j['gold_id'] == pending['gold_id']
                                               and j['prediction_index'] == pending['prediction_index'])
    gold = next(g for g in key['case']['gold_claims'] if g['id'] == pending['gold_id'])
    prediction = key['record']['report']['claims'][pending['prediction_index']]
    assert prediction['citations'] in gold['evidence_sets']
    assert evidence_covered(GoldClaim.model_validate(gold), prediction, key['case']['context_passages'])
    assert not any(m['gold_id'] == pending['gold_id'] and m['prediction_index'] == pending['prediction_index']
                   for m in key['record']['score']['matches'])
    assert pending['actual_frozen_evidence_covered_result'] and not pending['strict_claim_pair_matched']
    assert pending['returned_quotes_equal_a_frozen_gold_evidence_set']
    assert pending['strict_joint_credit_for_this_pair'] is False
    print(json.dumps({'targeted_correction_sensitivity': 'IDENTICAL', 'corrections': 2,
                      'semantic_judgments_not_reperformed': True, 'new_inference_calls': 0}), flush=True)


def main():
    plan = read(FOLDER / 'experiment-plan.json')
    receipt = read(FOLDER / 'execution-receipt.json')
    assert digest(FOLDER / 'experiment-plan.json') == receipt['source_freeze_sha256']
    assert fingerprints() == plan['source_fingerprints'], 'exact_archived_source_required'
    runs = []
    for number, block in enumerate(receipt['original_blocks'], 1):
        if block['status'] == 'UNKNOWN_NO_RELAUNCH':
            continue
        folder = FOLDER / block['block']
        before = hashes(folder)
        assert before == block['run_artifact_hashes'], 'saved_run_changed'
        run = read_repeated_run(folder, repetition=number)
        assert run['config']['fingerprints'] == plan['source_fingerprints']
        assert run['config']['settings'] == plan['settings']
        assert hashes(folder) == before, 'replay_changed_saved_files'
        runs.append(run)
        print(json.dumps({'run': block['block'], 'byte_identical_files': len(before),
                          'new_inference_calls': 0}), flush=True)
    repeated = FOLDER / 'repeated-analysis.json'
    if repeated.exists():
        assert len(runs) == 3, 'repeated_analysis_requires_three_terminal_runs'
        existing = read(repeated)
        ids = read(FOLDER / 'repeat-case-ids.json')
        groups = {}
        for track in plan['tracks']:
            for approach in plan['approaches']:
                groups[approach + '/' + track] = analyze_repeated(
                    runs, case_ids=ids, approach=approach, track=track,
                    baseline=None if approach == 'heuristic' else 'heuristic',
                    seed=plan['seed'], samples=plan['bootstrap_samples'])
            groups['optimized-minus-minimal/' + track] = analyze_repeated(
                runs, case_ids=ids, approach='optimized', track=track, baseline='minimal',
                seed=plan['seed'], samples=plan['bootstrap_samples'])
        assert groups == existing['groups'], 'repeated_analysis_changed'
        print(json.dumps({'repeated_groups': len(groups), 'status': 'IDENTICAL',
                          'new_inference_calls': 0}), flush=True)
    if (FOLDER / 'semantic-audit-analysis.json').exists():
        assert runs and runs[0]['repetition'] == 1
        replay_audit(runs[0], plan)
    print(json.dumps({'status': 'OFFLINE_REPLAY_COMPLETE', 'new_inference_calls': 0}), flush=True)


if __name__ == '__main__':
    main()
