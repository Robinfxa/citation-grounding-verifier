"""Capture safe public-consumer evidence using temporary synthetic credentials only.

Run from the project root with:
uv run --frozen python tests/provider/offline_probe.py --output .multi-subflow/provider
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from cli_timing import PROCESS_TIMEOUT_SECONDS


async def provider_worker(auth_dir: str) -> None:
    import httpx

    from grounding.codex_provider import CodexProvider
    from grounding.contracts import StructuredRequest, VerificationError

    count = 0

    def transport(request):
        nonlocal count
        count += 1
        if count == 2:
            raise httpx.ConnectError("PROVIDER_SECRET_MARKER_DO_NOT_EMIT")
        event = {
            "type": "response.completed",
            "response": {
                "status": "completed",
                "model": "fixture-model",
                "usage": None,
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": '{"ok":true}'}],
                    }
                ],
            },
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="data: " + json.dumps(event) + "\n\n",
        )

    request = StructuredRequest("probe", {}, "PROVIDER_SECRET_MARKER_DO_NOT_EMIT", {})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = CodexProvider("fixture-model", auth_dir=auth_dir, client=client)
        first = await provider.generate(request)
        try:
            await provider.generate(request)
        except VerificationError as error:
            fault_code = error.code
        else:
            raise AssertionError("Injected failure was not observed")
        recovered = await provider.generate(request)
    result = {
        "success": json.loads(first.text) == {"ok": True},
        "fault_code": fault_code,
        "recovered": json.loads(recovered.text) == {"ok": True},
        "usage_unknown": not first.usage.complete,
        "inference_attempts": count,
    }
    assert result == {
        "success": True,
        "fault_code": "upstream_unavailable",
        "recovered": True,
        "usage_unknown": True,
        "inference_attempts": 3,
    }
    print(json.dumps(result))


def capture(output: Path) -> None:
    import cryptography
    import httpx
    import jwt

    root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "python": platform.python_version(),
        "httpx": httpx.__version__,
        "pyjwt": jwt.__version__,
        "cryptography": cryptography.__version__,
        "scope": "Offline fixtures; actual CLI subprocesses and loopback socket. No real auth or inference.",
        "sources": {},
        "fixtures": {},
        "runs": [],
    }
    for name in (
        "codex_auth.py",
        "codex_provider.py",
        "providers.py",
        "contracts.py",
        "diagnostics.py",
        "verifiers.py",
        "config.py",
    ):
        manifest["sources"][name] = hashlib.sha256(
            (root / "src/grounding" / name).read_bytes()
        ).hexdigest()
    for name in ("cli_fixture.py", "cli_timing.py", "offline_probe.py"):
        manifest["fixtures"][name] = hashlib.sha256(
            Path(__file__).with_name(name).read_bytes()
        ).hexdigest()
    executable = str(Path(sys.executable).with_name("grounding-auth"))
    with tempfile.TemporaryDirectory(prefix="grounding-provider-probe-") as temporary:
        directory = Path(temporary)
        hook = directory / "hooks"
        hook.mkdir()
        (hook / "sitecustomize.py").write_text("from cli_fixture import install\ninstall()\n")
        auth_dir = str(directory / "credentials")
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(hook), str(Path(__file__).parent)]),
            "GROUNDING_AUTH_DIR": auth_dir,
            "GROUNDING_AUTH_PROFILE": "default",
            "GROUNDING_DIAGNOSTICS": "true",
            "PROVIDER_PROBE_SCENARIO": "success",
        }

        def run(label, args, expected=0, *, scenario="success", sink_failure=False, worker=False):
            environment = {
                **env,
                "PROVIDER_PROBE_SCENARIO": scenario,
                "PROVIDER_PROBE_FAIL_SINK": "1" if sink_failure else "0",
            }
            command = (
                [sys.executable, __file__, "--worker-auth-dir", auth_dir]
                if worker
                else ([executable, *args])
            )
            if worker:
                environment.pop("PYTHONPATH", None)
            result = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
                timeout=PROCESS_TIMEOUT_SECONDS,
            )
            combined = result.stdout + result.stderr
            assert not any(
                marker in combined
                for marker in (
                    "PROVIDER_SECRET_MARKER_DO_NOT_EMIT",
                    "synthetic-",
                    "eyJ",
                    "Traceback",
                )
            )
            assert result.returncode == expected, f"Unexpected exit for {label}"
            json.loads(result.stdout)
            for line in result.stderr.splitlines():
                json.loads(line)
            (output / f"{label}.stdout.json").write_text(result.stdout)
            (output / f"{label}.stderr.jsonl").write_text(result.stderr)
            manifest["runs"].append(
                {
                    "name": label,
                    "exit_code": result.returncode,
                    "command": "provider.generate ×3"
                    if worker
                    else "grounding-auth " + " ".join(args),
                    "fixture": scenario,
                    "sink_failure": sink_failure,
                }
            )

        run("login-success", ["login", "--timeout-seconds", "3"])
        run("status", ["status"])
        run("models", ["models"])
        run("provider-success-failure-recovery", [], worker=True)
        run("logout-success", ["logout"])
        run(
            "login-network-failure",
            ["login", "--timeout-seconds", "3"],
            1,
            scenario="network_failure",
        )
        run("login-missing-scope", ["login", "--timeout-seconds", "3"], scenario="missing_scope")
        run("models-missing-scope", ["models"], 1)
        run("login-failed-sink", ["login", "--timeout-seconds", "3"], sink_failure=True)
        run("logout-remote-failure", ["logout"], scenario="revocation_failure")
        run(
            "login-recovery-success",
            ["login", "--profile", "recovery-fixture", "--timeout-seconds", "3"],
            scenario="invalid_grant_recovery",
        )
        run(
            "login-token-rejected",
            ["login", "--timeout-seconds", "3"],
            1,
            scenario="token_rejected",
        )
        run("login-jwt-nonce", ["login", "--timeout-seconds", "3"], 1, scenario="jwt_nonce")
        run("login-jwks-rejected", ["login", "--timeout-seconds", "3"], 1, scenario="jwks_rejected")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "runs": len(manifest["runs"]),
                "all_expected_exits": True,
                "secrets_in_records": False,
                "real_network": "loopback only",
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".multi-subflow/provider"))
    parser.add_argument("--worker-auth-dir")
    args = parser.parse_args()
    if args.worker_auth_dir:
        asyncio.run(provider_worker(args.worker_auth_dir))
    else:
        capture(args.output)
