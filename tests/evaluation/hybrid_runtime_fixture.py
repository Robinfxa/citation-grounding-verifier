"""Real Jev verifier + native adapter with local HTTPX responses, through the CLI."""
from __future__ import annotations

import argparse
import json
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import patch

import httpx
from test_hybrid import choice

from grounding.config import Settings
from grounding.contracts import ProviderResult, RunStats, TokenUsage, VerificationError
from grounding.jev_provider import JevProvider
from grounding.verifiers import build_verifier
from grounding_eval import cli, runner
from grounding_eval.dataset import load_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['success', 'failure', 'recovery', 'protocol'])
    parser.add_argument('dataset', type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    case = load_dataset(args.dataset)[0]
    settings = Settings(provider='codex', model='fixed-llm', max_provider_attempts=4,
                        transport_retries=0, jev_api_key='FAKE_JEV_SECRET', diagnostics=True)

    def wire(request):
        body = json.loads(request.content)
        assert body['model'] == 'jev-1.14.0'
        answers = {}
        for key, question in body['questions'].items():
            index = int(key.split('_')[1])
            options = tuple(question['criteria'])
            confidence = .6 if index == 1 and key.endswith('_relation') else 1.0
            selected = ('INSUFFICIENT_EVIDENCE' if key.endswith('_unsupported_reason') else
                        next(o for o in options if o != 'NO_ADEQUATE_BUNDLE')
                        if key.endswith('_selection') else case.gold_claims[index].verdict)
            decision = choice(selected, options, confidence)
            answers[key] = {'type': 'choice', 'choice': selected, 'confidence': confidence,
                            'probabilities': decision.probabilities}
            if args.scenario == 'protocol' and key.endswith('_relation'):
                answers[key]['confidence'] = None
        return httpx.Response(200, json={'model': 'jev-1.14.0', 'answers': answers,
                                         'usage': {'input_tokens': 100, 'output_tokens': 10}})

    class LLM:
        name, model = 'codex', 'fixed-llm'

        async def generate(self, request):
            if request.schema_name == 'atomic_claims':
                assert request.payload == {'generated_answer': case.generated_answer}
                payload = {'claims': [{'claim_text': g.claim_text, 'answer_quote': g.claim_text}
                                      for g in case.gold_claims]}
            else:
                assert set(request.payload) <= {'context_passages', 'claims', 'validation_errors'}
                assert request.payload['context_passages'] == case.context_passages
                if args.scenario == 'failure':
                    error = VerificationError('upstream_timeout', stats=RunStats(
                        usage=TokenUsage(11, 2), response_models=(self.model,)))
                    error.add_note('FAKE_JEV_SECRET\nFORGED_JEV')
                    raise error
                payload = {'judgments': [{
                    'claim_id': item['claim_id'], 'verdict': case.gold_claims[item['claim_id']].verdict,
                    'reasoning': 'Offline response.',
                    'citations': [x.model_dump() for x in case.gold_claims[item['claim_id']].evidence_sets[0]]
                    if case.gold_claims[item['claim_id']].evidence_sets else [],
                } for item in request.payload['claims']]}
            return ProviderResult(json.dumps(payload), TokenUsage(11, 2), self.model)

        async def aclose(self):
            pass

    async def run(**kwargs):
        async with AsyncExitStack() as stack:
            verifiers = {}
            for name in kwargs['approaches']:
                client = await stack.enter_async_context(httpx.AsyncClient(transport=httpx.MockTransport(wire)))
                verifiers[name] = build_verifier(name, settings=settings, provider=LLM(),
                    decision_provider=JevProvider(api_key='FAKE_JEV_SECRET', client=client))
            return await runner.run_benchmark(**kwargs, verifiers=verifiers)

    with patch.object(Settings, 'from_env', return_value=settings), patch.object(cli, 'run_benchmark', run):
        return cli.main(args.arguments)


if __name__ == '__main__':
    raise SystemExit(main())
