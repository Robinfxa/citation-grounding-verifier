from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from cli_timing import PROCESS_TIMEOUT_SECONDS

from grounding.codex_auth import CredentialStore


@pytest.fixture
def offline_cli(tmp_path):
    hook = tmp_path / "hooks"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text("from cli_fixture import install\ninstall()\n")
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(hook), str(Path(__file__).parent)]),
        GROUNDING_AUTH_DIR=str(tmp_path / "cli-credentials"),
        GROUNDING_AUTH_PROFILE="default",
    )
    executable = str(Path(sys.executable).with_name("grounding-auth"))
    invocation = 0

    def run(*args, scenario="success", extra_env=None):
        nonlocal invocation
        invocation += 1
        phase_file = tmp_path / f"cli-phases-{invocation}.jsonl"
        try:
            output = subprocess.run(
                [executable, *args],
                capture_output=True,
                text=True,
                timeout=PROCESS_TIMEOUT_SECONDS,
                env={
                    **env,
                    "PROVIDER_PROBE_SCENARIO": scenario,
                    "PROVIDER_PROBE_PHASE_FILE": str(phase_file),
                    **(extra_env or {}),
                },
            )
        except subprocess.TimeoutExpired:
            phases = phase_file.read_text() if phase_file.exists() else "before hook startup"
            pytest.fail("CLI subprocess timed out; safe fixture phases: " + phases)
        assert "PROVIDER_SECRET_MARKER_DO_NOT_EMIT" not in output.stdout + output.stderr
        assert "synthetic-" not in output.stdout + output.stderr
        assert "eyJ" not in output.stdout + output.stderr
        assert "Traceback" not in output.stdout + output.stderr
        return output

    return run, env


async def test_public_cli_full_loopback_login_catalog_status_and_revocation(offline_cli):
    run, env = offline_cli
    logged_in = run("login", "--timeout-seconds", "3")
    assert logged_in.returncode == 0 and json.loads(logged_in.stdout)["plan_enabled"]
    status = run("status")
    assert status.returncode == 0 and json.loads(status.stdout)["registered"]
    catalog = run("models")
    assert (
        catalog.returncode == 0
        and json.loads(catalog.stdout)["models"][0]["slug"] == "fixture-model"
    )
    logged_out = run("logout")
    assert (
        logged_out.returncode == 0 and json.loads(logged_out.stdout)["remote_revocation_confirmed"]
    )
    store = CredentialStore(auth_dir=env["GROUNDING_AUTH_DIR"])
    assert store.load().client_id == "oaiapp_test" and store.load().access_token is None


def test_public_cli_recovers_invalid_grant_with_one_fresh_authorization(offline_cli):
    run, env = offline_cli
    result = run("login", "--timeout-seconds", "3", scenario="invalid_grant_recovery")
    assert result.returncode == 0 and json.loads(result.stdout)["plan_enabled"]
    records = [json.loads(line) for line in result.stderr.splitlines()]
    assert len([item for item in records if item["outcome"] == "reauthorizing"]) == 1
    exchange = [
        item
        for item in records
        if item["stage"] == "auth_token_exchange" and item["event"] == "end"
    ]
    assert [item["outcome"] for item in exchange] == ["failure", "success"]
    assert records[-1]["stage"] == "auth_login" and records[-1]["outcome"] == "success"
    assert CredentialStore(auth_dir=env["GROUNDING_AUTH_DIR"]).load().client_id == "oaiapp_test"


def test_public_cli_second_invalid_grant_stops_without_saving_identity(offline_cli):
    run, env = offline_cli
    result = run("login", "--timeout-seconds", "3", scenario="token_rejected")
    assert (
        result.returncode == 1
        and json.loads(result.stdout)["error"]["code"] == "authentication_failed"
    )
    records = [json.loads(line) for line in result.stderr.splitlines()]
    assert len([item for item in records if item["outcome"] == "reauthorizing"]) == 1
    failures = [
        item
        for item in records
        if item["stage"] == "auth_token_exchange" and item["outcome"] == "failure"
    ]
    assert len(failures) == 2 and all(item["reason"] == "oauth_invalid_grant" for item in failures)
    assert not CredentialStore(auth_dir=env["GROUNDING_AUTH_DIR"]).path.exists()
    assert not any(item["stage"] in {"auth_id_token", "auth_jwks"} for item in records)


def test_public_cli_accepts_real_sized_model_catalog(offline_cli):
    run, _ = offline_cli
    assert run("login", "--timeout-seconds", "3").returncode == 0
    result = run("models", scenario="large_catalog")
    assert result.returncode == 0
    assert [entry["slug"] for entry in json.loads(result.stdout)["models"]] == [
        f"fixture-model-{index}" for index in range(7)
    ]


@pytest.mark.parametrize(
    "scenario,code",
    [("network_failure", "upstream_unavailable"), ("callback_denied", "authorization_denied")],
)
def test_public_cli_login_failure_is_safe_and_does_not_save_tokens(offline_cli, scenario, code):
    run, env = offline_cli
    result = run("login", "--timeout-seconds", "3", scenario=scenario)
    assert result.returncode == 1 and json.loads(result.stdout)["error"]["code"] == code
    assert not CredentialStore(auth_dir=env["GROUNDING_AUTH_DIR"]).status()["signed_in"]
    assert json.loads(result.stderr.splitlines()[-1])["error_code"] == code


def test_public_cli_missing_permission_and_remote_revocation_failure_are_explicit(offline_cli):
    run, _ = offline_cli
    result = run("login", "--timeout-seconds", "3", scenario="missing_scope")
    assert result.returncode == 0 and not json.loads(result.stdout)["plan_enabled"]
    blocked = run("models")
    assert (
        blocked.returncode == 1
        and json.loads(blocked.stdout)["error"]["code"] == "plan_not_authorized"
    )
    assert run("login", "--timeout-seconds", "3").returncode == 0
    result = run("logout", scenario="revocation_failure")
    assert (
        result.returncode == 0 and json.loads(result.stdout)["remote_revocation_confirmed"] is False
    )
    assert "Disconnect" in json.loads(result.stdout)["action"]


def test_cli_default_buffering_survives_diagnostic_sink_failure(offline_cli):
    run, _ = offline_cli
    result = run("login", "--timeout-seconds", "3", extra_env={"PROVIDER_PROBE_FAIL_SINK": "1"})
    assert result.returncode == 0 and json.loads(result.stdout)["plan_enabled"]
    assert result.stderr == ""
    result = run("logout", extra_env={"PROVIDER_PROBE_FAIL_SINK": "1"})
    assert result.returncode == 0 and not json.loads(result.stdout)["signed_in"]
    assert result.stderr == ""


def test_refresh_rotates_once_across_two_independent_cli_processes(offline_cli, tmp_path):
    run, env = offline_cli
    assert run("login", "--timeout-seconds", "3").returncode == 0
    store = CredentialStore(auth_dir=env["GROUNDING_AUTH_DIR"])
    store.save(replace(store.load(), expires_at=0))
    counter = tmp_path / "refresh-count.txt"
    environment = {
        **env,
        "PROVIDER_PROBE_SCENARIO": "success",
        "PROVIDER_PROBE_COUNTER": str(counter),
    }
    executable = str(Path(sys.executable).with_name("grounding-auth"))
    processes = [
        subprocess.Popen(
            [executable, "models"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
        assert process.returncode == 0 and json.loads(stdout)["models"]
        assert "synthetic-" not in stdout + stderr and "Traceback" not in stderr
    assert counter.read_text().splitlines() == ["refresh"]
    assert store.load().refresh_token == "synthetic-rotated-refresh"
