"""Machine-readable stdout and payload-free diagnostics on stderr."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

from grounding.config import Settings
from grounding.contracts import VerificationError
from grounding.diagnostics import operation
from grounding_eval.dataset import (
    DEFAULT_DATASET,
    DatasetError,
    file_hash,
    load_dataset,
    validate_cases,
)
from grounding_eval.diagnostics import emit
from grounding_eval.provenance import strict_json
from grounding_eval.runner import (
    EvaluationError,
    json_text,
    read_saved_run,
    regenerate_report,
    run_benchmark,
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, '{"error_code":"invalid_arguments"}\n')


def parser() -> argparse.ArgumentParser:
    result = Parser(description="Reproducible context-only grounding evaluation")
    commands = result.add_subparsers(dest="command", required=True, parser_class=Parser)
    validate = commands.add_parser("validate", help="Check dataset schema and annotation integrity")
    validate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    run = commands.add_parser("run", help="Run actual verifier implementations into a new directory")
    run.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    run.add_argument("--approaches", default="heuristic,minimal,optimized")
    run.add_argument("--format-version", type=int, choices=[2, 3], default=2,
                     help="Jev approaches require explicit format 3")
    run.add_argument("--provider-budgets", type=Path,
                     help="Format-3 JSON provider allocations and measured-only dollar policy")
    run.add_argument("--split", choices=["dev", "test", "all", "diagnostic"], default="test",
                     help="all selects dev/test only; use --dataset for the separate diagnostic file")
    run.add_argument("--track", choices=["oracle", "end-to-end", "both"], default="both")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--seed", type=int, default=20261015)
    run.add_argument("--bootstrap-samples", type=int, default=10_000)
    run.add_argument("--prices", type=Path, help="Explicit dated JSON API price snapshot; never used for Codex")
    run.add_argument("--case-ids-file", type=Path, help="Frozen JSON array of unique case IDs")
    run.add_argument("--max-total-provider-attempts", type=int,
                     help="Total provider attempt allowance, including retries; required for model runs")
    run.add_argument("--stop-on-model-error", action="store_true",
                     help="Leave later model jobs uncalled after the first model failure")
    report = commands.add_parser("report", help="Regenerate summary from complete saved records")
    report.add_argument("run_dir", type=Path)
    sweep = commands.add_parser("sweep", help="Replay observed Jev gates on development only; no inference")
    sweep.add_argument("run_dir", type=Path)
    sweep.add_argument("--thresholds", required=True, help="Comma-separated thresholds varied together")
    for command in (validate, run, report, sweep):
        command.add_argument("--quiet", action="store_true", help="Disable diagnostic events")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    stage = {"validate": "eval_validate", "run": "eval_run", "report": "eval_report", "sweep": "eval_report"}[args.command]
    with operation(enabled=not args.quiet, new=True) as op:
        if args.command != "run":
            emit(op, stage, "start", "started")
        try:
            if args.command == "validate":
                cases = load_dataset(args.dataset, main=args.dataset.resolve() == DEFAULT_DATASET.resolve())
                result = {"status": "VALID", "dataset_sha256": file_hash(args.dataset),
                          **validate_cases(cases, main=args.dataset.resolve() == DEFAULT_DATASET.resolve())}
            elif args.command == "run":
                settings = Settings.from_env(include_jev=any(
                    name in {"jev_minimal", "jev_optimized"} for name in args.approaches.split(",")))
                if args.quiet:
                    settings = replace(settings, diagnostics=False)
                prices = strict_json(args.prices.read_text()) if args.prices else None
                provider_budgets = strict_json(args.provider_budgets.read_text()) if args.provider_budgets else None
                case_ids = strict_json(args.case_ids_file.read_text()) if args.case_ids_file else None
                if args.case_ids_file and not isinstance(case_ids, list):
                    raise EvaluationError("invalid_arguments")
                result = asyncio.run(run_benchmark(
                    dataset_path=args.dataset, output=args.output,
                    approaches=args.approaches.split(","), split=args.split, track=args.track,
                    seed=args.seed, bootstrap_samples=args.bootstrap_samples, settings=settings, prices=prices,
                    case_ids=case_ids, max_total_provider_attempts=args.max_total_provider_attempts,
                    stop_on_model_error=args.stop_on_model_error, format_version=args.format_version,
                    provider_budgets=provider_budgets))
            elif args.command == "report":
                result = regenerate_report(args.run_dir)
            else:
                from grounding_eval.confidence import threshold_sweep

                config, records, cases, _ = read_saved_run(args.run_dir)
                if config["format_version"] != 3:
                    raise EvaluationError("invalid_arguments")
                result = threshold_sweep(config, records, cases, [float(v) for v in args.thresholds.split(",")])
            if args.command != "run":
                emit(op, stage, "end", "success")
            sys.stdout.write(json_text(result))
            return 0 if result.get("completion", {}).get("status", "COMPLETE") == "COMPLETE" else 2
        except DatasetError:
            code = "dataset_invalid"
        except EvaluationError as exc:
            code = str(exc)
        except VerificationError as exc:
            code = exc.code
        except (ValueError, OSError):
            code = "invalid_arguments"
        except Exception:
            code = "internal_error"
        emit(op, stage, "end", "failure", error_code=code)
        sys.stdout.write(json.dumps({"error_code": code}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
