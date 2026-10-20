"""Explicit project configuration; importing this module never reads credentials."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from grounding.contracts import VerificationError


@dataclass(frozen=True)
class Settings:
    approach: str = "minimal"
    provider: str = "openai"
    model: str | None = None
    api_key: str | None = field(default=None, repr=False)
    base_url: str = field(default="https://api.openai.com/v1", repr=False)
    auth_profile: str = "default"
    auth_dir: str | None = field(default=None, repr=False)
    provider_timeout: float = 30.0
    operation_timeout: float = 60.0
    max_provider_attempts: int = 6
    transport_retries: int = 1
    retry_delay: float = 0.25
    max_output_tokens: int = 8_192
    diagnostics: bool = True
    jev_model: str = "jev-1.14.0"
    jev_api_key: str | None = field(default=None, repr=False)
    jev_base_url: str = field(default="https://api.typesafe.ai/v1", repr=False)
    jev_label_threshold: float = 0.8
    jev_evidence_threshold: float = 0.8
    jev_reason_threshold: float = 0.8
    jev_fallback: bool = True
    jev_max_request_bytes: int = 256_000
    jev_max_question_bytes: int = 128_000

    def __post_init__(self) -> None:
        valid = self.approach in {"heuristic", "minimal", "optimized", "jev_minimal", "jev_optimized"}
        valid &= self.provider in {"openai", "codex"}
        valid &= self.model is None or (isinstance(self.model, str) and bool(self.model.strip()))
        valid &= self.api_key is None or isinstance(self.api_key, str)
        valid &= isinstance(self.base_url, str) and bool(self.base_url.strip())
        valid &= isinstance(self.auth_profile, str) and bool(self.auth_profile.strip())
        valid &= self.auth_dir is None or isinstance(self.auth_dir, str)
        for value in (self.provider_timeout, self.operation_timeout):
            valid &= type(value) in (int, float) and math.isfinite(value) and 0 < value <= 600
        valid &= (
            type(self.retry_delay) in (int, float)
            and math.isfinite(self.retry_delay)
            and 0 <= self.retry_delay <= 10
        )
        for value, low, high in (
            (self.max_provider_attempts, 1, 6),
            (self.transport_retries, 0, 1),
            (self.max_output_tokens, 1, 32_768),
        ):
            valid &= type(value) is int and low <= value <= high
        valid &= type(self.diagnostics) is bool
        if not valid:
            raise VerificationError("not_configured")
        if self.approach in {"jev_minimal", "jev_optimized"}:
            self.validate_jev()

    def validate_jev(self) -> None:
        """Validate optional settings when a caller actually selects a Jev method."""
        valid = self.jev_model == "jev-1.14.0"
        valid &= self.jev_api_key is None or isinstance(self.jev_api_key, str)
        valid &= isinstance(self.jev_base_url, str) and bool(self.jev_base_url.strip())
        valid &= type(self.jev_fallback) is bool
        for value in (self.jev_label_threshold, self.jev_evidence_threshold, self.jev_reason_threshold):
            valid &= type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
        for value in (self.jev_max_request_bytes, self.jev_max_question_bytes):
            valid &= type(value) is int and 1 <= value <= 1_048_576
        if valid:
            valid &= self.jev_max_question_bytes <= self.jev_max_request_bytes
        if not valid:
            raise VerificationError("not_configured")

    @classmethod
    def from_env(
        cls, *, dotenv_path: str | Path | None = ".env", include_jev: bool | None = None
    ) -> Settings:
        """Load only the deliberately selected .env, with process environment precedence.

        No parent-directory search, private auth-file read, or mutation of os.environ.
        Pass dotenv_path=None to disable .env loading entirely.
        include_jev=True also loads Jev settings for callers selecting methods
        separately (for example, the benchmark CLI's --approaches option).
        """
        try:
            values = dict(dotenv_values(dotenv_path, interpolate=False)) if dotenv_path else {}
            values.update(os.environ)
            diagnostics = values.get("GROUNDING_DIAGNOSTICS", "true").lower()
            if diagnostics not in {"true", "false", "1", "0"}:
                raise ValueError
            approach = values.get("GROUNDING_APPROACH", "minimal")
            use_jev = include_jev is True or approach in {"jev_minimal", "jev_optimized"}
            jev_values = {}
            if use_jev:
                fallback = values.get("GROUNDING_JEV_FALLBACK", "true").lower()
                if fallback not in {"true", "false", "1", "0"}:
                    raise ValueError
                jev_values = {
                    "jev_model": values.get("TYPESAFE_MODEL") or "jev-1.14.0",
                    "jev_api_key": values.get("TYPESAFE_API_KEY") or None,
                    "jev_base_url": values.get("TYPESAFE_BASE_URL") or "https://api.typesafe.ai/v1",
                    "jev_label_threshold": float(values.get("GROUNDING_JEV_LABEL_THRESHOLD", "0.8")),
                    "jev_evidence_threshold": float(
                        values.get("GROUNDING_JEV_EVIDENCE_THRESHOLD", "0.8")
                    ),
                    "jev_reason_threshold": float(values.get("GROUNDING_JEV_REASON_THRESHOLD", "0.8")),
                    "jev_fallback": fallback in {"true", "1"},
                    "jev_max_request_bytes": int(values.get("GROUNDING_JEV_MAX_REQUEST_BYTES", "256000")),
                    "jev_max_question_bytes": int(
                        values.get("GROUNDING_JEV_MAX_QUESTION_BYTES", "128000")
                    ),
                }
            settings = cls(
                approach=approach,
                provider=values.get("GROUNDING_PROVIDER", "openai"),
                model=values.get("GROUNDING_MODEL") or values.get("OPENAI_MODEL") or None,
                api_key=values.get("OPENAI_API_KEY") or None,
                base_url=values.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
                auth_profile=values.get("GROUNDING_AUTH_PROFILE") or "default",
                auth_dir=values.get("GROUNDING_AUTH_DIR") or None,
                provider_timeout=float(values.get("GROUNDING_PROVIDER_TIMEOUT", "30")),
                operation_timeout=float(values.get("GROUNDING_OPERATION_TIMEOUT", "60")),
                max_provider_attempts=int(values.get("GROUNDING_MAX_PROVIDER_ATTEMPTS", "6")),
                transport_retries=int(values.get("GROUNDING_TRANSPORT_RETRIES", "1")),
                retry_delay=float(values.get("GROUNDING_RETRY_DELAY", "0.25")),
                max_output_tokens=int(values.get("GROUNDING_MAX_OUTPUT_TOKENS", "8192")),
                diagnostics=diagnostics in {"true", "1"},
                **jev_values,
            )
            if use_jev:
                settings.validate_jev()
            return settings
        except (OSError, ValueError, TypeError, AttributeError):
            raise VerificationError("not_configured") from None
