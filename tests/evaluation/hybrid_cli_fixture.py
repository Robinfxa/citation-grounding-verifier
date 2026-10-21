"""Subprocess-only offline boundary for the real CLI; no product fixture flag."""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from test_hybrid import ScriptedHybrid

from grounding.config import Settings
from grounding_eval import cli, runner
from grounding_eval.dataset import load_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['success', 'failure', 'recovery'])
    parser.add_argument('dataset', type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    settings = Settings(provider='codex', model='fixed-llm', max_provider_attempts=3,
                        api_key='FAKE_JEV_SECRET\nFORGED_JEV', jev_api_key='FAKE_JEV_SECRET',
                        jev_base_url='https://FAKE_JEV_SECRET.invalid', diagnostics=True)
    case = load_dataset(args.dataset)[0]

    async def run(**kwargs):
        return await runner.run_benchmark(**kwargs, verifiers={
            approach: ScriptedHybrid(case, fail=args.scenario == 'failure')
            for approach in kwargs['approaches']})

    # This substitutes only Settings and the public verifier seam. Parsing, runner,
    # persistence, report guards, scoring, logs and exit behavior are production code.
    with patch.object(Settings, 'from_env', return_value=settings), patch.object(cli, 'run_benchmark', run):
        return cli.main(args.arguments)


if __name__ == '__main__':
    raise SystemExit(main())
