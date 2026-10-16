import hashlib
import json

import pytest


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_v2(directory):
    directory.mkdir(parents=True, exist_ok=True)
    text = 'Queue café blocks at capacity. A timeout is optional.\n'
    (directory / 'source.txt').write_text(text, encoding='utf-8')
    (directory / 'LICENSE').write_text('Example reuse is allowed.\n', encoding='utf-8')
    answer = 'Queue café blocks at capacity. A timeout is required. Queue café is blue.'
    claims = [
        ('Queue café blocks at capacity.', 'SUPPORTED', 'Queue café blocks at capacity.'),
        ('A timeout is required.', 'CONTRADICTED', 'A timeout is optional.'),
        ('Queue café is blue.', 'UNSUPPORTED', None),
    ]
    case = {
        'id': 'real-queue', 'family_id': 'queue-doc', 'split': 'dev', 'category': 'supported',
        'tags': ['scope', 'unicode'],
        'provenance': {
            'kind': 'real_source', 'fictional': False, 'language': 'en',
            'origin': 'generated_from_real_source', 'source_ids': ['queue-source'],
            'generator': {'kind': 'program', 'name': 'offline-test', 'version': '1'},
            'annotation_version': 'annotation-1',
        },
        'context_passages': [text], 'generated_answer': answer,
        'gold_claims': [
            {'id': f'c{i}', 'claim_text': claim, 'aliases': [], 'verdict': verdict,
             'rationale': 'Offline annotation fixture.',
             'evidence_sets': [[{'index': 0, 'quote': quote}]] if quote else [],
             'answer_anchor': {'quote': claim, 'start': answer.index(claim),
                               'end': answer.index(claim) + len(claim)}}
            for i, (claim, verdict, quote) in enumerate(claims)
        ],
    }
    path = directory / 'development.jsonl'
    path.write_text(json.dumps(case, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest = {
        'format_version': 2, 'schema_version': '2', 'dataset_version': 'offline-1',
        'annotation_version': 'annotation-1', 'dataset_file': path.name,
        'dataset_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'layout': [{'split': 'dev', 'category': 'supported', 'cases': 1}],
        'sources': [{
            'id': 'queue-source', 'family_id': 'queue-doc',
            'url': 'https://example.org/immutable/queue', 'revision': 'offline-1',
            'license': 'Example permissive notice', 'license_path': 'LICENSE',
            'license_sha256': sha('Example reuse is allowed.\n'),
            'raw_path': 'source.txt', 'raw_sha256': sha(text),
        }],
        'passage_maps': [{'case_id': case['id'], 'passage_index': 0,
                          'source_id': 'queue-source', 'start': 0, 'end': len(text),
                          'text_sha256': sha(text)}],
    }
    manifest_path = path.with_suffix('.manifest.json')
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    return path, case, manifest


@pytest.fixture
def v2_fixture(tmp_path):
    return write_v2(tmp_path / 'v2')
