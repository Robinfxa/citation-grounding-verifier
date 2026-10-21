import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from grounding_eval.dataset import Case, DatasetError, load_dataset


def rewrite(path, case, manifest):
    path.write_text(json.dumps(case, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest['dataset_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


def test_real_source_unicode_anchors_and_typed_manifest(v2_fixture):
    path, raw, _ = v2_fixture
    case = load_dataset(path, main=True)[0]
    assert case.provenance.kind == 'real_source'
    assert case.gold_claims[1].answer_anchor.start == raw['generated_answer'].index('A timeout')


@pytest.mark.parametrize('defect', ['missing_anchor', 'boolean_offset', 'wrong_anchor',
                                  'unknown_provenance', 'fictional', 'blank_generator'])
def test_real_schema_rejects_untrusted_metadata(v2_fixture, defect):
    _, raw, _ = v2_fixture
    raw = copy.deepcopy(raw)
    if defect == 'missing_anchor':
        raw['gold_claims'][0].pop('answer_anchor')
    elif defect == 'boolean_offset':
        raw['gold_claims'][0]['answer_anchor']['start'] = False
    elif defect == 'wrong_anchor':
        raw['gold_claims'][0]['answer_anchor']['end'] -= 1
    elif defect == 'unknown_provenance':
        raw['provenance']['arbitrary'] = {'accepted': True}
    elif defect == 'fictional':
        raw['provenance']['fictional'] = True
    else:
        raw['provenance']['generator']['name'] = ' '
    with pytest.raises(ValidationError):
        Case.model_validate(raw)


@pytest.mark.parametrize('defect', [
    'source_bytes', 'license_bytes', 'unknown_manifest', 'layout', 'dataset_hash',
    'source_id', 'family', 'offset', 'passage_hash', 'annotation_version',
    'duplicate_map', 'missing_map', 'parent_path', 'absolute_path', 'symlink', 'float_version',
])
def test_manifest_rejects_changed_or_malicious_bindings(v2_fixture, tmp_path, defect):
    path, raw, manifest = v2_fixture
    if defect == 'source_bytes':
        (path.parent / 'source.txt').write_text('SECRET_SOURCE\nFORGED_EVENT')
    elif defect == 'license_bytes':
        (path.parent / 'LICENSE').write_text('Altered license')
    elif defect == 'unknown_manifest':
        manifest['custom_metadata'] = {'permit': True}
    elif defect == 'layout':
        manifest['layout'][0]['cases'] = 2
    elif defect == 'dataset_hash':
        manifest['dataset_sha256'] = '0' * 64
    elif defect == 'source_id':
        manifest['passage_maps'][0]['source_id'] = 'missing'
    elif defect == 'family':
        manifest['sources'][0]['family_id'] = 'another'
    elif defect == 'offset':
        manifest['passage_maps'][0]['end'] -= 1
    elif defect == 'passage_hash':
        manifest['passage_maps'][0]['text_sha256'] = '0' * 64
    elif defect == 'annotation_version':
        manifest['annotation_version'] = 'unfrozen'
    elif defect == 'duplicate_map':
        manifest['passage_maps'] *= 2
    elif defect == 'missing_map':
        manifest['passage_maps'] = []
    elif defect == 'parent_path':
        manifest['sources'][0]['raw_path'] = '../outside.txt'
    elif defect == 'absolute_path':
        manifest['sources'][0]['license_path'] = str(tmp_path / 'outside.txt')
    elif defect == 'float_version':
        manifest['format_version'] = 2.0
    else:
        outside = tmp_path / 'outside.txt'
        outside.write_text('SECRET_SOURCE')
        link = path.parent / 'linked.txt'
        link.symlink_to(outside)
        manifest['sources'][0]['raw_path'] = link.name
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(DatasetError) as caught:
        load_dataset(path)
    assert 'SECRET_SOURCE' not in str(caught.value)


def test_real_source_requires_manifest(v2_fixture):
    path, _, _ = v2_fixture
    path.with_suffix('.manifest.json').unlink()
    with pytest.raises(DatasetError, match='manifest'):
        load_dataset(path)


def test_identical_raw_source_cannot_leak_across_declared_families(v2_fixture):
    path, raw, manifest = v2_fixture
    other = copy.deepcopy(raw)
    other.update(id='mirror-case', family_id='invented-mirror-family', split='test')
    other['provenance']['source_ids'] = ['mirror-source']
    mirrored_source = {**manifest['sources'][0], 'id': 'mirror-source',
                       'family_id': other['family_id'], 'url': 'https://mirror.example.org/document'}
    manifest['sources'].append(mirrored_source)
    manifest['layout'].append({'split': 'test', 'category': 'supported', 'cases': 1})
    manifest['passage_maps'].append({**manifest['passage_maps'][0], 'case_id': other['id'],
                                    'source_id': 'mirror-source'})
    path.write_text(''.join(json.dumps(case, ensure_ascii=False) + '\n' for case in [raw, other]),
                    encoding='utf-8')
    manifest['dataset_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(DatasetError, match='manifest'):
        load_dataset(path)
