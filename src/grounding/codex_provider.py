"""Single-attempt public Responses/SSE adapter for an application SIWC grant."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx

from grounding.codex_auth import AuthError, CredentialStore, diagnostic_scope, emit_diagnostic
from grounding.contracts import ProviderResult, StructuredRequest, VerificationError
from grounding.diagnostics import request_id

RESPONSES_URL = "https://api.openai.com/v1/responses"
_UPSTREAM_CODES = {
    "subscription_sharing_usage_limit_exceeded": "quota_exhausted",
    "insufficient_quota": "quota_exhausted",
    "subscription_sharing_usage_unavailable": "upstream_unavailable",
    "subscription_sharing_user_unavailable": "upstream_unavailable",
    "subscription_sharing_unsupported_capability": "unsupported_capability",
    "subscription_sharing_route_not_supported": "unsupported_capability",
    "subscription_sharing_user_not_eligible": "plan_not_authorized",
    "subscription_sharing_invalid_user": "authentication_failed",
    "chatpass_v2_scope_not_authorized": "plan_not_authorized",
    "chatpass_v2_invalid_authorization_context": "plan_not_authorized",
    "rate_limit_exceeded": "rate_limited",
    "server_error": "upstream_unavailable",
    "model_not_found": "unsupported_capability",
}


def _error(status: int, body: dict[str, Any]) -> VerificationError:
    error = body.get("error", body)
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and code in _UPSTREAM_CODES:
        return VerificationError(_UPSTREAM_CODES[code])
    if status == 401:
        return VerificationError("authentication_failed")
    if status == 403:
        return VerificationError("plan_not_authorized")
    if status == 429:
        return VerificationError("rate_limited")
    if status in {408, 504}:
        return VerificationError("upstream_timeout")
    if status >= 500:
        return VerificationError("upstream_unavailable")
    return VerificationError("provider_protocol_error")


def _encoded_size(data: dict[str, Any]) -> int:
    try:
        return len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise VerificationError("provider_protocol_error") from None


class _CompletedOutput:
    """Retain finalized items only, never construct content from text deltas."""

    def __init__(self, max_bytes: int) -> None:
        self.response_id: str | None = None
        self.started: list[tuple[str, str, Any]] = []
        self.item_ids: set[str] = set()
        self.finished: dict[int, dict[str, Any]] = {}
        self.content_indices: dict[int, int] = {}
        self.size = 0
        self.max_bytes = max_bytes

    def record(self, event: dict[str, Any]) -> None:
        kind = event["type"]
        if kind in {"response.created", "response.in_progress"}:
            response = event.get("response")
            identity = response.get("id") if isinstance(response, dict) else None
            if not isinstance(identity, str) or not identity:
                raise VerificationError("provider_protocol_error")
            if kind == "response.created" and self.response_id is None:
                self.response_id = identity
            elif kind == "response.created" or identity != self.response_id:
                raise VerificationError("provider_protocol_error")
            return
        if kind not in {
            "response.output_item.added",
            "response.output_item.done",
            "response.content_part.added",
            "response.content_part.done",
            "response.output_text.delta",
            "response.output_text.done",
        }:
            return
        index = event.get("output_index")
        if self.response_id is None or type(index) is not int or index < 0:
            raise VerificationError("provider_protocol_error")
        if kind in {"response.output_item.added", "response.output_item.done"}:
            item = event.get("item")
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or not item["id"]
                or not isinstance(item.get("type"), str)
            ):
                raise VerificationError("provider_protocol_error")
            identity = (item["id"], item["type"], item.get("role"))
            if kind == "response.output_item.added":
                if index != len(self.started) or item["id"] in self.item_ids:
                    raise VerificationError("provider_protocol_error")
                self.started.append(identity)
                self.item_ids.add(item["id"])
                return
            if (
                index >= len(self.started)
                or index in self.finished
                or identity != self.started[index]
                # AIDEV-NOTE: a paired reasoning done item may omit its optional
                # status. Assistant messages still require explicit completion.
                or (
                    item.get("status") != "completed"
                    and not (item["type"] == "reasoning" and item.get("status") is None)
                )
            ):
                raise VerificationError("provider_protocol_error")
            if index in self.content_indices:
                content = item.get("content")
                if not isinstance(content, list) or self.content_indices[index] >= len(content):
                    raise VerificationError("provider_protocol_error")
            self.size += _encoded_size(item)
            if self.size > self.max_bytes:
                raise VerificationError("response_too_large")
            self.finished[index] = item
            return
        content_index = event.get("content_index")
        if (
            index >= len(self.started)
            or index in self.finished
            or event.get("item_id") != self.started[index][0]
            or type(content_index) is not int
            or content_index < 0
        ):
            raise VerificationError("provider_protocol_error")
        self.content_indices[index] = max(self.content_indices.get(index, -1), content_index)

    def finish(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        if (
            self.response_id is None
            or response.get("id") != self.response_id
            or not self.started
            or len(self.finished) != len(self.started)
        ):
            raise VerificationError("provider_protocol_error")
        return [self.finished[index] for index in range(len(self.started))]


class CodexProvider:
    name = "codex"

    def __init__(
        self,
        model: str | None,
        timeout_seconds: float = 30,
        *,
        profile: str = "default",
        auth_dir: str | Path | None = None,
        auth_store: CredentialStore | None = None,
        client: httpx.AsyncClient | None = None,
        parser: Callable[[dict[str, Any]], ProviderResult] | None = None,
        max_stream_bytes: int = 4_194_304,
        max_event_bytes: int = 1_048_576,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        if min(max_stream_bytes, max_event_bytes, max_response_bytes) <= 0:
            raise ValueError("response byte limits must be positive")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._store = auth_store
        self._profile = profile
        self._auth_dir = auth_dir
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds, follow_redirects=False, trust_env=False
        )
        self._owns_client = client is None
        self._parser = parser
        self._max_stream = max_stream_bytes
        self._max_event = max_event_bytes
        self._max_response = max_response_bytes

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @diagnostic_scope
    async def generate(self, request: StructuredRequest) -> ProviderResult:
        operation_id, started = request_id(), time.monotonic()
        stream_opened = False
        emit_diagnostic("codex_inference", "start", operation_id, started)
        try:
            if not self.model:
                raise VerificationError("not_configured")
            async with asyncio.timeout(self.timeout_seconds):
                try:
                    store = self._store or CredentialStore(self._profile, self._auth_dir)
                    token = await store.access_token(self._client, self.timeout_seconds)
                except AuthError as error:
                    code = (
                        error.code
                        if error.code
                        in {
                            "not_configured",
                            "plan_not_authorized",
                            "upstream_timeout",
                            "rate_limited",
                            "upstream_unavailable",
                            "authentication_failed",
                            "provider_protocol_error",
                        }
                        else "authentication_failed"
                    )
                    raise VerificationError(code) from None
                body = {
                    "model": self.model,
                    "store": False,
                    "stream": True,
                    "instructions": request.instructions,
                    "input": [
                        {"role": "user", "content": json.dumps(request.payload, ensure_ascii=False)}
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": request.schema_name,
                            "strict": True,
                            "schema": request.schema,
                        }
                    },
                }
                async with self._client.stream(
                    "POST",
                    RESPONSES_URL,
                    headers={"Authorization": "Bearer " + token, "Accept": "text/event-stream"},
                    json=body,
                    timeout=self.timeout_seconds,
                    follow_redirects=False,
                ) as response:
                    if response.status_code != 200:
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(raw) + len(chunk) > min(self._max_response, 65_536):
                                raise VerificationError("response_too_large")
                            raw.extend(chunk)
                        try:
                            data = json.loads(raw)
                        except (ValueError, RecursionError):
                            data = {}
                        raise _error(response.status_code, data if isinstance(data, dict) else {})
                    # AIDEV-NOTE: the public SIWC direct route can omit Content-Type;
                    # framing and a real completed response still govern success.
                    media_type = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    if media_type and media_type != "text/event-stream":
                        raise VerificationError("provider_protocol_error")
                    stream_opened = True
                    emit_diagnostic("codex_inference", "stream_open", operation_id, started)
                    result = await self._consume(response)
            emit_diagnostic("codex_inference", "success", operation_id, started)
            return result
        except (TimeoutError, httpx.TimeoutException):
            emit_diagnostic("codex_inference", "failure", operation_id, started, "upstream_timeout")
            error = VerificationError("upstream_timeout")
            error.retryable = not stream_opened
            raise error from None
        except httpx.HTTPError:
            emit_diagnostic(
                "codex_inference", "failure", operation_id, started, "upstream_unavailable"
            )
            error = VerificationError("upstream_unavailable")
            error.retryable = not stream_opened
            raise error from None
        except VerificationError as error:
            # AIDEV-NOTE: the service owns retries and consults this flag. Once
            # streaming opens, a retry could repeat already-consumed plan usage.
            if stream_opened:
                error.retryable = False
            emit_diagnostic("codex_inference", "failure", operation_id, started, error.code)
            raise
        except asyncio.CancelledError:
            emit_diagnostic("codex_inference", "cancelled", operation_id, started)
            raise

    async def _events(self, response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        total = 0
        pending = bytearray()
        lines: list[bytes] = []
        event_size = 0
        event_name = None

        async def chunks():
            async for chunk in response.aiter_bytes():
                yield chunk, False
            yield b"", True

        async for chunk, at_eof in chunks():
            total += len(chunk)
            if total > self._max_stream:
                raise VerificationError("response_too_large")
            pending.extend(chunk)
            while True:
                # SSE accepts LF, CRLF and CR. Keep a trailing CR until the next
                # chunk so a split CRLF cannot create a false event boundary.
                positions = [pos for pos in (pending.find(b"\n"), pending.find(b"\r")) if pos >= 0]
                if not positions:
                    break
                position = min(positions)
                if (
                    pending[position : position + 1] == b"\r"
                    and position == len(pending) - 1
                    and not at_eof
                ):
                    break
                width = 2 if pending[position : position + 2] == b"\r\n" else 1
                line = bytes(pending[:position])
                del pending[: position + width]
                event_size += len(line) + width
                if event_size > self._max_event:
                    raise VerificationError("response_too_large")
                if not line:
                    if lines:
                        raw = b"\n".join(lines)
                        if raw == b"[DONE]":
                            raise VerificationError("provider_protocol_error")
                        try:
                            event = json.loads(raw)
                        except (ValueError, UnicodeError, RecursionError):
                            raise VerificationError("provider_protocol_error") from None
                        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                            raise VerificationError("provider_protocol_error")
                        if event_name and event_name != event["type"]:
                            raise VerificationError("provider_protocol_error")
                        yield event
                    lines, event_size, event_name = [], 0, None
                elif not line.startswith(b":"):
                    field, _, value = line.partition(b":")
                    if value.startswith(b" "):
                        value = value[1:]
                    if field == b"data":
                        lines.append(value)
                    elif field == b"event":
                        try:
                            event_name = value.decode("ascii")
                        except UnicodeError:
                            raise VerificationError("provider_protocol_error") from None
            if event_size + len(pending) > self._max_event:
                raise VerificationError("response_too_large")
        # AIDEV-NOTE: deltas and [DONE] are never a substitute for a framed
        # response.completed, even when output_item.done already carries content.
        raise VerificationError("provider_protocol_error")

    async def _consume(self, response: httpx.Response) -> ProviderResult:
        output: _CompletedOutput | None = _CompletedOutput(self._max_response)
        output_error: str | None = None
        async for event in self._events(response):
            kind = event["type"]
            if kind in {"response.refusal.delta", "response.refusal.done"}:
                raise VerificationError("model_refused")
            if kind == "response.incomplete":
                raise VerificationError("model_incomplete")
            if kind in {"error", "response.failed"}:
                body = event.get("response") if kind == "response.failed" else event
                raise _error(0, body if isinstance(body, dict) else {})
            if kind == "response.completed":
                data = event.get("response")
                if not isinstance(data, dict):
                    raise VerificationError("provider_protocol_error")
                try:
                    if (
                        data.get("status") != "completed"
                        or data.get("error")
                        or data.get("incomplete_details")
                    ):
                        raise VerificationError("provider_protocol_error")
                    # AIDEV-NOTE: SIWC can send output=[] after finalized item events.
                    # Recover only that exact shape, with paired completed items and
                    # matching response identity; the shared final parser stays strict.
                    if isinstance(data.get("output"), list) and not data["output"]:
                        if output_error is not None:
                            raise VerificationError(output_error)
                        assert output is not None
                        data = {**data, "output": output.finish(data)}
                    if _encoded_size(data) > self._max_response:
                        raise VerificationError("response_too_large")
                    parser = self._parser
                    if parser is None:
                        from grounding.providers import parse_response

                        parser = parse_response
                    return parser(data)
                except VerificationError as error:
                    # AIDEV-NOTE: local assembly failure does not erase terminal
                    # measurements. Reuse shared validation, including unknowns.
                    if error.stats is None:
                        from grounding.providers import response_stats

                        error.stats = response_stats(data)
                    raise
            if output is not None:
                try:
                    output.record(event)
                except VerificationError as error:
                    # A complete terminal output remains authoritative. Retain a
                    # safe failure for the empty-output path and release candidates.
                    output_error, output = error.code, None
        raise VerificationError("provider_protocol_error")
