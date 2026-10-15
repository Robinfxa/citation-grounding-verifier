import sys
from types import SimpleNamespace

import pytest

from grounding.config import Settings
from grounding.contracts import VerificationError
from grounding.verifiers import build_verifier


def test_env_loading_is_explicit_nonmutating_and_respects_precedence(tmp_path, monkeypatch):
    for key in ("GROUNDING_PROVIDER", "GROUNDING_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY",
                "GROUNDING_AUTH_PROFILE", "GROUNDING_AUTH_DIR", "GROUNDING_APPROACH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "fallback-model")
    path = tmp_path / ".env"
    path.write_text(
        "GROUNDING_PROVIDER=codex\nGROUNDING_MODEL=dotenv-model\nOPENAI_API_KEY=SECRET_KEY\n"
        "GROUNDING_AUTH_PROFILE=work\nGROUNDING_AUTH_DIR=/private/test\nGROUNDING_APPROACH=minimal\n"
    )
    from_file = Settings.from_env(dotenv_path=path)
    assert from_file.model == "dotenv-model"
    assert from_file.auth_profile == "work"
    assert from_file.auth_dir == "/private/test"
    assert from_file.approach == "minimal"
    assert "SECRET_KEY" not in repr(from_file)
    assert "/private/test" not in repr(from_file)
    monkeypatch.setenv("GROUNDING_MODEL", "process-model")
    assert Settings.from_env(dotenv_path=path).model == "process-model"
    monkeypatch.delenv("GROUNDING_MODEL")
    assert Settings.from_env(dotenv_path=None).model == "fallback-model"
    assert Settings.from_env(dotenv_path=None).provider == "openai"


@pytest.mark.parametrize("changes", [
    {"provider_timeout": float("nan")}, {"operation_timeout": float("inf")},
    {"provider_timeout": 0}, {"max_provider_attempts": 7}, {"max_provider_attempts": True},
    {"transport_retries": 2}, {"retry_delay": -1}, {"max_output_tokens": 0},
])
def test_nonfinite_or_unbounded_limits_fail_with_safe_configuration_error(changes):
    with pytest.raises(VerificationError) as caught:
        Settings(**changes)
    assert caught.value.code == "not_configured"


def test_lazy_codex_factory_passes_auth_and_shared_model_settings(monkeypatch):
    observed = []

    class CodexFixture:
        name = "codex"

        def __init__(self, **kwargs):
            observed.append(kwargs)
            self.model = kwargs["model"]

    monkeypatch.setitem(sys.modules, "grounding.codex_provider", SimpleNamespace(CodexProvider=CodexFixture))
    settings = Settings(provider="codex", model="same-model", auth_profile="work", auth_dir="/test")
    minimal = build_verifier("minimal", settings=settings)
    optimized = build_verifier("optimized", settings=settings)
    assert minimal.provider.model == optimized.provider.model == "same-model"
    assert observed == [{"model": "same-model", "timeout_seconds": 30.0,
                         "profile": "work", "auth_dir": "/test"}] * 2
