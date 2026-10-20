import pytest

from grounding.config import Settings
from grounding.contracts import VerificationError


def test_jev_settings_are_opt_in_and_pin_the_experiment():
    assert Settings().approach == "minimal"
    for name in ("jev_minimal", "jev_optimized"):
        assert Settings(approach=name).jev_model == "jev-1.14.0"


def test_separate_type_safe_credentials_and_literal_env_values(tmp_path, monkeypatch):
    keys = ("GROUNDING_APPROACH", "TYPESAFE_API_KEY", "TYPESAFE_MODEL", "TYPESAFE_BASE_URL",
            "GROUNDING_JEV_FALLBACK", "GROUNDING_JEV_LABEL_THRESHOLD",
            "GROUNDING_JEV_EVIDENCE_THRESHOLD", "GROUNDING_JEV_REASON_THRESHOLD",
            "GROUNDING_JEV_MAX_REQUEST_BYTES", "GROUNDING_JEV_MAX_QUESTION_BYTES",
            "OPENAI_API_KEY")
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text("GROUNDING_APPROACH=jev_minimal\nTYPESAFE_API_KEY=synthetic-${UNCHANGED}\n"
                    "OPENAI_API_KEY=synthetic-other-provider\nGROUNDING_JEV_FALLBACK=false\n"
                    "GROUNDING_JEV_LABEL_THRESHOLD=0.9\nGROUNDING_JEV_EVIDENCE_THRESHOLD=0.95\n"
                    "GROUNDING_JEV_REASON_THRESHOLD=0.85\nGROUNDING_JEV_MAX_REQUEST_BYTES=8000\n"
                    "GROUNDING_JEV_MAX_QUESTION_BYTES=4000\n")
    config = Settings.from_env(dotenv_path=path)
    assert config.jev_api_key == "synthetic-${UNCHANGED}"
    assert config.api_key == "synthetic-other-provider"
    assert "synthetic" not in repr(config)
    assert not config.jev_fallback
    assert (config.jev_label_threshold, config.jev_evidence_threshold,
            config.jev_reason_threshold) == (0.9, 0.95, 0.85)
    assert (config.jev_max_request_bytes, config.jev_max_question_bytes) == (8000, 4000)
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-process")
    assert Settings.from_env(dotenv_path=path).jev_api_key == "synthetic-process"
    assert Settings.from_env(dotenv_path=None).api_key is None


@pytest.mark.parametrize("changes", [
    {"jev_model": "jev-latest"}, {"jev_model": "jev-preview"}, {"jev_model": "jev-1.13.0"},
    {"jev_label_threshold": True}, {"jev_evidence_threshold": float("nan")},
    {"jev_reason_threshold": float("inf")}, {"jev_label_threshold": -0.1},
    {"jev_evidence_threshold": 1.01}, {"jev_fallback": "false"},
    {"jev_max_request_bytes": True}, {"jev_max_question_bytes": 0},
    {"jev_max_request_bytes": 1_048_577},
    {"jev_max_request_bytes": 100, "jev_max_question_bytes": 101},
])
def test_bad_or_unbounded_jev_configuration_fails_safely(changes):
    with pytest.raises(VerificationError) as caught:
        Settings(approach="jev_minimal", **changes)
    assert caught.value.code == "not_configured"


@pytest.mark.parametrize("value", ["sometimes", "", "2"])
def test_fallback_env_requires_an_explicit_boolean(value, monkeypatch):
    monkeypatch.setenv("GROUNDING_APPROACH", "jev_minimal")
    monkeypatch.setenv("GROUNDING_JEV_FALLBACK", value)
    with pytest.raises(VerificationError) as caught:
        Settings.from_env(dotenv_path=None)
    assert caught.value.code == "not_configured"


@pytest.mark.parametrize("approach", ["minimal", "optimized", "heuristic"])
@pytest.mark.parametrize("key,value", [
    ("TYPESAFE_MODEL", "other-jev-version"),
    ("GROUNDING_JEV_LABEL_THRESHOLD", "invalid-unused-threshold"),
    ("GROUNDING_JEV_FALLBACK", "invalid-unused-boolean"),
    ("GROUNDING_JEV_MAX_REQUEST_BYTES", "invalid-unused-size"),
])
def test_legacy_methods_ignore_unused_jev_environment(approach, key, value, monkeypatch):
    monkeypatch.setenv("GROUNDING_APPROACH", approach)
    monkeypatch.setenv(key, value)
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-unused")
    settings = Settings.from_env(dotenv_path=None)
    assert settings.approach == approach
    assert settings.jev_api_key is None
    with pytest.raises(VerificationError) as caught:
        Settings.from_env(dotenv_path=None, include_jev=True)
    assert caught.value.code == "not_configured"


def test_cli_opt_in_loads_jev_configuration_with_legacy_default(monkeypatch):
    monkeypatch.setenv("GROUNDING_APPROACH", "minimal")
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-selected")
    monkeypatch.setenv("GROUNDING_JEV_LABEL_THRESHOLD", "0.93")
    settings = Settings.from_env(dotenv_path=None, include_jev=True)
    assert settings.approach == "minimal"
    assert settings.jev_api_key == "synthetic-selected"
    assert settings.jev_label_threshold == 0.93


def test_direct_caller_validates_jev_when_selecting_it_later():
    settings = Settings(jev_model="not-used-by-minimal")
    assert settings.approach == "minimal"
    with pytest.raises(VerificationError) as caught:
        settings.validate_jev()
    assert caught.value.code == "not_configured"
