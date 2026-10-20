"""Reconstruct private scoring inputs and full claim gold from metadata offsets.

First run rebuild_ragtruth.py to acquire the fixed original records. This
second, stdlib-only step applies the visible Summary instruction and rebuilds
gold anchor/evidence strings locally. It does not distribute upstream prose.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_text(value, expected):
    if digest(value.encode()) != expected:
        raise ValueError('text_hash_mismatch')
    return value


def interval(value, spec):
    start, end = spec['start'], spec['end']
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(value)):
        raise ValueError('invalid_unicode_interval')
    return verify_text(value[start:end], spec['utf8_sha256'])


def rebuild(recipe, raw_input, output, recipe_directory):
    raw_bytes = raw_input.read_bytes()
    if digest(raw_bytes) != recipe['raw_acquisition_input_sha256']:
        raise ValueError('raw_acquisition_hash_mismatch')
    raw = [json.loads(line) for line in raw_bytes.decode().splitlines()]
    by_id = {str(r['response_record']['id']): r for r in raw}
    cases, blind, sealed = [], [], []
    for spec in recipe['records']:
        row = by_id[spec['response_id']]
        response, source = row['response_record'], row['source_record']
        if str(response['source_id']) != spec['source_id']:
            raise ValueError('source_identity_mismatch')
        original_answer = verify_text(response['response'], spec['original_response_utf8_sha256'])
        context = verify_text(source['source_info'], spec['original_context_utf8_sha256'])
        prompt = verify_text(source['prompt'], spec['original_prompt_utf8_sha256'])
        instruction = prompt.splitlines()[0]
        if source['task_type'] != 'Summary' or not instruction.startswith('Summarize the following news within '):
            raise ValueError('unexpected_original_task_instruction')
        prefix = 'Question: ' + instruction + '\n\nAnswer: '
        if len(prefix) != spec['prefix_unicode_characters']:
            raise ValueError('adapter_prefix_length_mismatch')
        answer = verify_text(prefix + original_answer, spec['adapted_answer_utf8_sha256'])
        gold = []
        for annotation in spec['claims']:
            span = annotation['original_response_interval']
            anchor = interval(original_answer, span)
            evidence = [[{'index': item['passage_index'], 'quote': interval(context, item)}
                         for item in evidence_set]
                        for evidence_set in annotation['source_interval_sets']]
            if any(item['index'] != 0 for evidence_set in evidence for item in evidence_set):
                raise ValueError('unexpected_passage_index')
            gold.append(dict(id=annotation['claim_id'], claim_text=annotation['proposition'],
                             aliases=annotation['acceptable_aliases'], verdict=annotation['label'],
                             evidence_sets=evidence, rationale=annotation['annotation_reason'],
                             answer_anchor=dict(quote=anchor, start=span['start'] + len(prefix), end=span['end'] + len(prefix))))
        case = dict(spec['case_shell'])
        case.update(context_passages=[context], generated_answer=answer, gold_claims=gold)
        cases.append(case)
        blind.append(dict(id=case['id'], context_passages=[context], generated_answer=answer,
                          origin=dict(kind='actual_natural_response', corpus='RAGTruth', task_type='Summary',
                                      upstream_response_id=response['id'], source_id=response['source_id'],
                                      upstream_model=response['model'], upstream_split=response['split'], upstream_quality=response['quality'])))
        sealed.append(dict(id=case['id'], gold_claims=gold))
    outputs = {'private-cases.jsonl': cases, 'blind.jsonl': blind, 'sealed-gold.jsonl': sealed}
    membership = recipe.get('scoring_membership')
    scoring_ids = None
    if membership is not None:
        all_ids = [case['id'] for case in cases]
        scoring_ids = membership['ordered_scoring_ids']
        diagnostic_ids = membership['ordered_non_scoring_diagnostic_ids']
        if (membership['ordered_all_ids'] != all_ids or len(set(all_ids)) != len(all_ids)
                or len(set(scoring_ids)) != len(scoring_ids)
                or len(set(diagnostic_ids)) != len(diagnostic_ids)
                or set(scoring_ids) & set(diagnostic_ids)
                or set(scoring_ids) | set(diagnostic_ids) != set(all_ids)
                or [ident for ident in all_ids if ident in scoring_ids] != scoring_ids
                or [ident for ident in all_ids if ident in diagnostic_ids] != diagnostic_ids):
            raise ValueError('scoring_membership_mismatch')
        for filename, rows in [('scoring-cases.jsonl', cases), ('scoring-blind.jsonl', blind),
                               ('scoring-sealed-gold.jsonl', sealed)]:
            outputs[filename] = [row for row in rows if row['id'] in scoring_ids]
    encoded = {name: ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows).encode() for name, rows in outputs.items()}
    if membership is not None:
        encoded['scoring-membership.json'] = (json.dumps(membership, ensure_ascii=False, indent=2) + '\n').encode()
    actual_hashes = {name: digest(data) for name, data in encoded.items()}
    if actual_hashes != recipe['expected_outputs']:
        raise ValueError('scoring_output_hash_mismatch')
    license_bytes = (recipe_directory / recipe['repository_license_file']).read_bytes()
    if digest(license_bytes) != recipe['repository_license_sha256']:
        raise ValueError('repository_license_hash_mismatch')
    sources, maps = [], []
    for case, spec in zip(cases, recipe['records']):
        ident = spec['source_id']
        if not ident.isdecimal():
            raise ValueError('unexpected_source_id')
        context = case['context_passages'][0]
        relative_path = 'raw-contexts/' + ident + '.txt'
        encoded[relative_path] = context.encode()
        sources.append(dict(id=ident, family_id=case['family_id'],
                            url='https://raw.githubusercontent.com/ParticleMedia/RAGTruth/' + recipe['upstream_revision'] + '/dataset/source_info.jsonl#source_id=' + ident,
                            revision=recipe['upstream_revision'],
                            license='RAGTruth repository MIT notice retained; underlying third-party text rights unverified; private acquisition only',
                            license_path='licenses/RAGTruth-MIT', license_sha256=digest(license_bytes),
                            raw_path=relative_path, raw_sha256=digest(context.encode())))
        maps.append(dict(case_id=case['id'], passage_index=0, source_id=ident,
                         start=0, end=len(context), text_sha256=digest(context.encode())))
    versions = {case['provenance']['annotation_version'] for case in cases}
    if len(versions) != 1:
        raise ValueError('annotation_version_mismatch')
    manifest_hashes = {}
    dataset_names = ['private-cases.jsonl'] + (['scoring-cases.jsonl'] if membership is not None else [])
    for filename in dataset_names:
        rows = outputs[filename]
        selected_ids = {case['id'] for case in rows}
        selected_maps = [mapping for mapping in maps if mapping['case_id'] in selected_ids]
        source_ids = {mapping['source_id'] for mapping in selected_maps}
        layout = Counter((case['split'], case['category']) for case in rows)
        manifest = dict(format_version=2, schema_version='2', dataset_version=recipe['recipe_version'],
                        annotation_version=next(iter(versions)), dataset_file=filename,
                        dataset_sha256=actual_hashes[filename],
                        layout=[dict(split=s, category=c, cases=n) for (s, c), n in sorted(layout.items())],
                        sources=[source for source in sources if source['id'] in source_ids],
                        passage_maps=selected_maps)
        manifest_name = Path(filename).stem + '.manifest.json'
        encoded[manifest_name] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
        manifest_hashes[manifest_name] = digest(encoded[manifest_name])
    encoded['licenses/RAGTruth-MIT'] = license_bytes
    for name, data in encoded.items():
        target = output / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError('refusing_to_replace_different_private_output')
    for name, data in encoded.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = dict(records=len(cases), claims=sum(len(c['gold_claims']) for c in cases),
                  recipe_version=recipe['recipe_version'], raw_acquisition_sha256=digest(raw_bytes),
                  private_output_sha256=actual_hashes,
                  private_manifest_sha256=manifest_hashes['private-cases.manifest.json'],
                  private_manifest_sha256_by_file=manifest_hashes,
                  private_manifest_source_format='Each raw-contexts file is the unchanged decoded source_info string from the fixed source_info.jsonl record, not the JSON serialization bytes. This exact field extraction is part of the reconstruction recipe.',
                  license_scope='Repository MIT notice is retained for repository material only; manifest loading is not a legal determination or a grant to redistribute underlying news. All reconstructed upstream text stays private.',
                  original_response_and_context_unchanged=True,
                  claim_annotation_status=recipe['independent_review_status'], human_review=recipe['human_review'],
                  inference_performed=False, redistribution='private_outputs_only')
    if membership is not None:
        report.update(primary_scoring_file='scoring-cases.jsonl', primary_scoring_cases=len(scoring_ids),
                      primary_scoring_claims=sum(len(c['gold_claims']) for c in outputs['scoring-cases.jsonl']),
                      non_scoring_diagnostic_cases=len(membership['ordered_non_scoring_diagnostic_ids']),
                      full12_is_not_primary_scoring=True)
    (output / 'rebuild-receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--raw-input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rebuild(json.loads(args.recipe.read_text()), args.raw_input, args.output, args.recipe.parent)))
