from __future__ import annotations

import asyncio
import copy
import json

import httpx
import pytest
from test_codex_stream import REQUEST, Chunks, completed, sse

from grounding.codex_provider import CodexProvider
from grounding.contracts import VerificationError


def direct_events():
    """Synthetic content with the lifecycle/index shapes of the safe live projection."""
    identity = {"output_index": 0, "content_index": 0, "item_id": "synthetic-item"}
    text = '{"ok":true}'
    item = {
        "id": "synthetic-item",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }
    response = {"id": "synthetic-response", "status": "in_progress", "output": []}
    events = [
        {"type": "response.created", "response": response},
        {"type": "response.in_progress", "response": copy.deepcopy(response)},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "status": "in_progress", "content": []},
        },
        {
            "type": "response.content_part.added",
            **identity,
            "part": {"type": "output_text", "text": ""},
        },
        *[
            {"type": "response.output_text.delta", **identity, "delta": piece}
            for piece in (text[:2], text[2:4], text[4:6], text[6:10], text[10:])
        ],
        {"type": "response.output_text.done", **identity, "text": text},
        {"type": "response.content_part.done", **identity, "part": item["content"][0]},
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        {
            "type": "response.completed",
            "response": {
                "id": response["id"],
                "status": "completed",
                "model": "returned-model",
                "output": [],
                "error": None,
                "incomplete_details": None,
                "usage": {
                    "input_tokens": 52,
                    "output_tokens": 14,
                    "input_tokens_details": {"cached_tokens": 0},
                },
            },
        },
    ]
    return [dict(event, sequence_number=index) for index, event in enumerate(events)]


async def generate(credentials, events, *, media_type=None, limits=None, parser=None):
    payload = b"".join(sse(event) for event in events)
    stream = Chunks([payload[index : index + 7] for index in range(0, len(payload), 7)])
    calls = []

    def transport(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"] == REQUEST.schema
        return httpx.Response(
            200, headers={} if media_type is None else {"content-type": media_type}, stream=stream
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        try:
            return await CodexProvider(
                "fixture-model",
                auth_store=credentials,
                client=client,
                parser=parser,
                **(limits or {}),
            ).generate(REQUEST)
        finally:
            assert len(calls) == 1 and stream.closed


@pytest.mark.parametrize("media_type", [None, "", "text/event-stream; charset=utf-8"])
async def test_observed_empty_terminal_uses_completed_items_and_terminal_usage(
    credentials, media_type
):
    result = await generate(credentials, direct_events(), media_type=media_type)
    assert json.loads(result.text) == {"ok": True}
    assert result.model == "returned-model" and result.usage.complete
    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cached_input_tokens,
    ) == (
        52,
        14,
        0,
    )


async def test_missing_media_type_accepts_complete_terminal_without_item_reconstruction(
    credentials,
):
    result = await generate(credentials, [completed()])
    assert json.loads(result.text) == {"ok": True}


@pytest.mark.parametrize(
    "media_type", ["application/json", "text/plain", "text/html", "application/octet-stream"]
)
async def test_explicit_incompatible_media_type_rejects_even_valid_sse(credentials, media_type):
    with pytest.raises(VerificationError) as error:
        await generate(credentials, direct_events(), media_type=media_type)
    assert error.value.code == "provider_protocol_error" and not error.value.retryable


async def test_complete_terminal_remains_authoritative_when_fallback_candidates_are_invalid(
    credentials,
):
    events = direct_events()
    events[2]["item"]["id"] = "different-candidate"
    events[-1]["response"]["output"] = completed(text='{"terminal":true}')["response"]["output"]
    result = await generate(credentials, events, media_type="text/event-stream")
    assert json.loads(result.text) == {"terminal": True}


async def test_paired_done_item_supplies_content_without_delta_or_text_done(credentials):
    events = direct_events()
    result = await generate(credentials, [events[index] for index in (0, 2, 11, 12)])
    assert json.loads(result.text) == {"ok": True}


async def test_item_done_content_and_terminal_usage_are_the_only_reconstruction_sources(
    credentials,
):
    events = direct_events()
    for event in events:
        if event["type"] == "response.output_text.delta":
            event["delta"] = "synthetic-secret"
        elif event["type"] == "response.output_text.done":
            event["text"] = "synthetic-secret"
        elif event["type"] == "response.content_part.done":
            event["part"] = {"type": "output_text", "text": "synthetic-secret"}
    events[11]["item"]["usage"] = {"input_tokens": 9999, "output_tokens": 9999}
    events[-1]["response"]["usage"] = None
    result = await generate(credentials, events)
    assert json.loads(result.text) == {"ok": True} and not result.usage.complete


async def test_completed_items_are_ordered_by_index_and_keep_reasoning_separate(credentials):
    events = direct_events()
    reasoning = {
        "id": "synthetic-reasoning",
        "type": "reasoning",
        "status": "completed",
        "summary": [],
    }
    added = {
        "type": "response.output_item.added",
        "output_index": 0,
        "item": {**reasoning, "status": "in_progress"},
    }
    done = {"type": "response.output_item.done", "output_index": 0, "item": reasoning}
    for event in events:
        if "output_index" in event:
            event["output_index"] = 1
    # The second item finishes first; final ordering still follows output_index.
    events.insert(2, added)
    events.insert(-1, done)
    assert json.loads((await generate(credentials, events)).text) == {"ok": True}


@pytest.mark.parametrize(
    "payload",
    [
        b'{"ok":true}',
        b"<html>synthetic-secret</html>",
        b"data: [DONE]\n\n",
        b"data: {invalid}\n\n",
    ],
)
async def test_missing_media_type_does_not_accept_non_sse_or_done_marker(credentials, payload):
    stream = Chunks([payload])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert (
        error.value.code == "provider_protocol_error"
        and not error.value.retryable
        and stream.closed
    )


def invalid_events(case):
    events = direct_events()
    added, done, final = events[2], events[11], events[12]["response"]
    if case == "missing-start":
        events = events[2:]
    elif case == "changed-progress-id":
        events[1]["response"]["id"] = "other-response"
    elif case == "changed-final-id":
        final["id"] = "other-response"
    elif case == "missing-final-id":
        del final["id"]
    elif case == "unpaired-done":
        del events[2]
    elif case == "unfinished-item":
        del events[11]
    elif case == "duplicate-added":
        events.insert(3, copy.deepcopy(added))
    elif case == "duplicate-done":
        events.insert(12, copy.deepcopy(done))
    elif case == "duplicate-created":
        events.insert(1, copy.deepcopy(events[0]))
    elif case == "changed-item-id":
        done["item"]["id"] = "other-item"
    elif case == "duplicate-item-id":
        events.insert(3, {**copy.deepcopy(added), "output_index": 1})
    elif case == "changed-item-type":
        done["item"]["type"] = "reasoning"
    elif case == "changed-item-role":
        done["item"]["role"] = "user"
    elif case in {"negative-index", "boolean-index", "string-index", "index-gap"}:
        added["output_index"] = {
            "negative-index": -1,
            "boolean-index": True,
            "string-index": "0",
            "index-gap": 1,
        }[case]
    elif case == "done-index-mismatch":
        done["output_index"] = 1
    elif case == "part-id-mismatch":
        events[3]["item_id"] = "other-item"
    elif case == "part-index-mismatch":
        events[3]["output_index"] = 1
    elif case == "content-index-mismatch":
        events[3]["content_index"] = 1
    elif case == "part-after-item-done":
        events.insert(12, copy.deepcopy(events[10]))
    elif case == "boolean-content-index":
        events[3]["content_index"] = True
    elif case in {"item-in-progress", "item-incomplete", "missing-item-status"}:
        done["item"]["status"] = "in_progress" if case == "item-in-progress" else "incomplete"
        if case == "missing-item-status":
            del done["item"]["status"]
    elif case == "final-error":
        final["error"] = {"code": "synthetic-secret"}
    elif case == "final-incomplete-details":
        final["incomplete_details"] = {"reason": "max_output_tokens"}
    elif case == "final-in-progress":
        final["status"] = "in_progress"
    elif case in {"null-output", "missing-output", "wrong-output-type"}:
        final["output"] = None if case == "null-output" else {}
        if case == "missing-output":
            del final["output"]
    elif case == "wrong-content-type":
        done["item"]["content"][0]["type"] = "input_text"
    elif case == "multiple-texts":
        done["item"]["content"].append({"type": "output_text", "text": "other"})
    elif case == "empty-content":
        done["item"]["content"] = []
    elif case == "missing-terminal":
        events.pop()
    elif case == "text-done-without-item-done":
        events = events[:11] + events[12:]
    else:
        raise AssertionError(case)
    return events


@pytest.mark.parametrize(
    "case",
    [
        "missing-start",
        "changed-progress-id",
        "changed-final-id",
        "missing-final-id",
        "unpaired-done",
        "unfinished-item",
        "duplicate-added",
        "duplicate-done",
        "duplicate-created",
        "changed-item-id",
        "duplicate-item-id",
        "changed-item-type",
        "changed-item-role",
        "negative-index",
        "boolean-index",
        "string-index",
        "index-gap",
        "done-index-mismatch",
        "part-id-mismatch",
        "part-index-mismatch",
        "content-index-mismatch",
        "part-after-item-done",
        "boolean-content-index",
        "item-in-progress",
        "item-incomplete",
        "missing-item-status",
        "final-error",
        "final-incomplete-details",
        "final-in-progress",
        "null-output",
        "missing-output",
        "wrong-output-type",
        "wrong-content-type",
        "multiple-texts",
        "empty-content",
        "missing-terminal",
        "text-done-without-item-done",
    ],
)
async def test_empty_terminal_never_repairs_missing_or_conflicting_completion_evidence(
    credentials, case
):
    with pytest.raises(VerificationError) as error:
        await generate(credentials, invalid_events(case), media_type="text/event-stream")
    assert error.value.code == "provider_protocol_error" and not error.value.retryable


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("response.failed", "quota_exhausted"),
        ("response.incomplete", "model_incomplete"),
        ("response.refusal.done", "model_refused"),
    ],
)
async def test_completed_item_cannot_override_failure_terminal(credentials, kind, expected):
    events = direct_events()[:-1]
    events.append(
        {"type": kind, "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}}
    )
    with pytest.raises(VerificationError) as error:
        await generate(credentials, events)
    assert error.value.code == expected and not error.value.retryable


async def test_reconstructed_refusal_still_uses_shared_parser(credentials):
    events = direct_events()
    events[11]["item"]["content"] = [{"type": "refusal", "refusal": "synthetic-secret"}]
    with pytest.raises(VerificationError) as error:
        await generate(credentials, events)
    assert error.value.code == "model_refused" and "synthetic-secret" not in str(error.value)
    assert error.value.stats.usage.input_tokens == 52


@pytest.mark.parametrize("adjustment", [0, -1])
async def test_reconstructed_final_object_respects_exact_existing_response_budget(
    credentials, adjustment
):
    events = direct_events()
    reconstructed = {**events[-1]["response"], "output": [events[11]["item"]]}
    limit = (
        len(json.dumps(reconstructed, ensure_ascii=False, allow_nan=False).encode()) + adjustment
    )
    if adjustment == 0:
        assert (await generate(credentials, events, limits={"max_response_bytes": limit})).text
    else:
        with pytest.raises(VerificationError) as error:
            await generate(credentials, events, limits={"max_response_bytes": limit})
        assert error.value.code == "response_too_large" and not error.value.retryable


@pytest.mark.parametrize("limit", ["max_stream_bytes", "max_event_bytes", "max_response_bytes"])
async def test_missing_media_type_keeps_all_existing_byte_limits(credentials, limit):
    with pytest.raises(VerificationError) as error:
        await generate(credentials, direct_events(), limits={limit: 32})
    assert error.value.code == "response_too_large" and not error.value.retryable


@pytest.mark.parametrize("value", ["\ud800", "\udfff", float("nan"), float("inf")])
async def test_invalid_completed_item_encoding_fails_with_safe_terminal_logs(
    credentials, capfd, value
):
    events = direct_events()
    events[11]["item"]["unsafe_metadata"] = value
    with pytest.raises(VerificationError) as error:
        await generate(credentials, events)
    assert error.value.code == "provider_protocol_error" and not error.value.retryable
    records = [json.loads(line) for line in capfd.readouterr().err.splitlines()]
    assert [record["event"] for record in records] == ["start", "provider_attempt", "end"]
    assert [record["outcome"] for record in records] == ["started", "started", "failure"]
    assert records[-1]["error_code"] == "provider_protocol_error"


@pytest.mark.parametrize(
    "failure,expected",
    [
        (httpx.ReadError("synthetic-secret"), "upstream_unavailable"),
        (httpx.ReadTimeout("synthetic-secret"), "upstream_timeout"),
    ],
)
async def test_done_item_before_read_failure_is_not_success_or_retryable(
    credentials, failure, expected
):
    stream = Chunks([b"".join(sse(event) for event in direct_events()[:-1])], failure=failure)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
    assert error.value.code == expected and not error.value.retryable and stream.closed


async def test_done_item_before_cancellation_still_closes_missing_media_type_stream(credentials):
    entered = asyncio.Event()
    stream = Chunks([b"".join(sse(event) for event in direct_events()[:-1])], wait=entered)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        task = asyncio.create_task(
            CodexProvider("model", auth_store=credentials, client=client).generate(REQUEST)
        )
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert stream.closed


async def test_done_item_before_total_timeout_is_not_success_and_cannot_retry(credentials):
    stream = Chunks([b"".join(sse(event) for event in direct_events()[:-1])], wait=asyncio.Event())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))
    ) as client:
        with pytest.raises(VerificationError) as error:
            await CodexProvider(
                "model", timeout_seconds=0.1, auth_store=credentials, client=client
            ).generate(REQUEST)
    assert error.value.code == "upstream_timeout" and not error.value.retryable and stream.closed
