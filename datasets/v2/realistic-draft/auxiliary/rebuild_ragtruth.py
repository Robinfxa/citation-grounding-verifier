"""Rebuild a fixed natural-response selection; no credentials or inference.

The upstream text is acquired separately under its applicable terms. Run with
--output pointing to a private working directory. This does not relicense text.
"""
import argparse
import hashlib
import json
import ssl
import urllib.request
from pathlib import Path

REVISION = 'c103204b9ce28d6bbad859304bf30de72b8ed8fe'
EXPECTED = {
    'response.jsonl':'e4c2e4ac24fff676d8984cc61c35d791612fadc58015335d97dd632375e18073',
    'source_info.jsonl':'0dffc26ea9f3c1c3d7c7e8336b56ef1646e3cec876edffcca3c9c624d12d578b',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rebuild(selection, output, cache=None):
    output.mkdir(parents=True, exist_ok=True)
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    tables = {}
    for name, expected in EXPECTED.items():
        candidate = (cache/name) if cache else (output/'upstream'/name)
        if candidate.exists():
            data = candidate.read_bytes()
        else:
            url = f'https://raw.githubusercontent.com/ParticleMedia/RAGTruth/{REVISION}/dataset/{name}'
            data = urllib.request.urlopen(url, context=context, timeout=90).read()
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(data)
        if digest(data) != expected:
            raise ValueError('upstream_hash_mismatch')
        tables[name] = [json.loads(x) for x in data.decode().splitlines()]
    responses = {str(r['id']):r for r in tables['response.jsonl']}
    sources = {str(s['source_id']):s for s in tables['source_info.jsonl']}
    rows = []
    for item in selection['records']:
        response = responses[item['response_id']]
        source = sources[response['source_id']]
        if digest(response['response'].encode()) != item['response_utf8_sha256']:
            raise ValueError('response_hash_mismatch')
        if not isinstance(source['source_info'], str):
            raise ValueError('expected_summary_source')
        context_text = source['source_info']
        if digest(context_text.encode()) != item['context_utf8_sha256']:
            raise ValueError('context_hash_mismatch')
        rows.append(dict(response_record=response, source_record=source,
                         adapted_input=dict(context_passages=[context_text], generated_answer=response['response']),
                         adaptation='Summary source_info unchanged as one passage; response unchanged. Upstream prompt retained separately, not silently inserted as evidence.',
                         original_span_coordinate_system='Unicode offsets in original response; no prefix or text cleanup',
                         original_context_range=dict(start=0, end=len(context_text)),
                         claim_annotation_status='not_performed'))
    path = output/'ragtruth-natural-selected.private.jsonl'
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    return dict(records=len(rows), private_artifact_sha256=digest(path.read_bytes()),
                upstream_files=EXPECTED, original_responses_preserved=True,
                annotation_status='not_performed', independent_review='not_performed')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--selection', type=Path, default=Path(__file__).with_name('ragtruth-selection.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path)
    args=parser.parse_args()
    print(json.dumps(rebuild(json.loads(args.selection.read_text()), args.output, args.cache)))
