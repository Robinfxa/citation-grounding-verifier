"""One-attempt OpenAI Responses transport and shared final-response parsing."""

from __future__ import annotations

import json
from typing import Any

import httpx

from grounding.contracts import (
    ProviderResult,
    RunStats,
    StructuredRequest,
    TokenUsage,
    VerificationError,
)

MAX_RESPONSE_BYTES = 2_097_152


def _usage(data: Any) -> TokenUsage:
    if not isinstance(data, dict):
        return TokenUsage(complete=False)
    incoming, outgoing = data.get("input_tokens"), data.get("output_tokens")
    details = data.get("input_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    valid_input = type(incoming) is int and incoming >= 0
    valid_output = type(outgoing) is int and outgoing >= 0
    valid_cached = type(cached) is int and cached >= 0 and valid_input and cached <= incoming
    return TokenUsage(
        incoming if valid_input else 0,
        outgoing if valid_output else 0,
        cached if valid_cached else 0,
        bool(valid_input and valid_output and valid_cached),
    )


def response_stats(data: dict) -> RunStats:
    """Read known response usage/model independently of output validation."""
    if not isinstance(data, dict):
        raise VerificationError("provider_protocol_error")
    usage = _usage(data.get("usage"))
    model = data.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        model = None
    if model is not None:
        try:
            model.encode("utf-8")
        except UnicodeError:
            model = None
    return RunStats(usage=usage, response_models=(model,) if model else ())


def parse_response(data: dict) -> ProviderResult:
    """Accept one complete final text, never an SDK-only output_text convenience field.

    Codex SSE uses this same boundary for response.completed.response. Invalid usage
    remains unknown rather than being coerced into billable token measurements.
    """
    stats = response_stats(data)

    def fail(code: str) -> None:
        raise VerificationError(code, stats=stats)

    if data.get("status") == "incomplete":
        fail("model_incomplete")
    if data.get("status") != "completed":
        fail("provider_protocol_error")
    output = data.get("output")
    if not isinstance(output, list):
        fail("provider_protocol_error")
    texts = []
    for item in output:
        if not isinstance(item, dict):
            fail("provider_protocol_error")
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message" or item.get("role") != "assistant":
            fail("provider_protocol_error")
        if item.get("status") != "completed" or not isinstance(item.get("content"), list):
            fail("provider_protocol_error")
        for content in item["content"]:
            if not isinstance(content, dict):
                fail("provider_protocol_error")
            if content.get("type") == "refusal":
                fail("model_refused")
            if content.get("type") != "output_text" or not isinstance(content.get("text"), str):
                fail("provider_protocol_error")
            texts.append(content["text"])
    if len(texts) != 1 or not texts[0].strip():
        fail("provider_protocol_error")
    try:
        text_bytes = len(texts[0].encode("utf-8"))
    except UnicodeError:
        fail("provider_protocol_error")
    if text_bytes > MAX_RESPONSE_BYTES:
        fail("response_too_large")
    return ProviderResult(
        text=texts[0], usage=stats.usage,
        model=stats.response_models[0] if stats.response_models else None,
    )


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        *,
        model: str | None,
        api_key: str | None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30,
        max_output_tokens: int = 8_192,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/responses"
        self._timeout = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._owns_client = client is None
        # HTTPX defaults to no transport retries and no redirect credential forwarding.
        self._client = client or httpx.AsyncClient(follow_redirects=False)

    async def generate(self, request: StructuredRequest) -> ProviderResult:
        if not self.model or not self._api_key:
            raise VerificationError("not_configured")
        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": request.instructions},
                {"role": "user", "content": json.dumps(request.payload, ensure_ascii=False)},
            ],
            "text": {"format": {
                "type": "json_schema", "name": request.schema_name,
                "schema": request.schema, "strict": True,
            }},
            "store": False,
            "stream": False,
            "max_output_tokens": self._max_output_tokens,
        }
        try:
            async with self._client.stream(
                "POST", self._url, json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            ) as response:
                status = response.status_code
                if status in (401, 403):
                    raise VerificationError("authentication_failed")
                if status == 429:
                    raise VerificationError("rate_limited")
                if status in (408, 504):
                    raise VerificationError("upstream_timeout")
                if status >= 500:
                    raise VerificationError("upstream_unavailable")
                if status != 200:
                    raise VerificationError("provider_protocol_error")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise VerificationError("response_too_large")
                    chunks.extend(chunk)
            data = json.loads(chunks)
        except httpx.TimeoutException:
            raise VerificationError("upstream_timeout") from None
        except (httpx.NetworkError, httpx.RemoteProtocolError, httpx.ProxyError):
            raise VerificationError("upstream_unavailable") from None
        except (httpx.InvalidURL, httpx.UnsupportedProtocol):
            raise VerificationError("not_configured") from None
        except (ValueError, UnicodeError, RecursionError, httpx.DecodingError):
            raise VerificationError("provider_protocol_error") from None
        return parse_response(data)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
