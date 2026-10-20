from __future__ import annotations

import asyncio
import copy
import json

import httpx
import pytest

from grounding.config import Settings
from grounding.contracts import DecisionRequest, TokenUsage, VerificationError
from grounding.jev_provider import JevProvider
from grounding.providers import MAX_RESPONSE_BYTES
from grounding.verifiers import build_verifier

MODEL = "jev-1.14.0"
SECRET = "JEV_SYNTHETIC_SECRET_DO_NOT_EMIT"
QUESTION = {
    "type": "choice",
    "instructions": {"claim": "Cedar resumes at one.", "task": "Judge the whole context."},
    "criteria": {"S": "Supported", "C": "Refuted", "U": "Insufficient or conflicting"},
}
REQUEST = DecisionRequest({"context": ["Cedar resumes at one. 中文。"]}, {"claim_0": QUESTION})


def answer():
    return {
        "type": "choice",
        "choice": "S",
        "confidence": 0.85,
        "probabilities": {"S": 0.9, "C": 0.05, "U": 0.05},
    }


def response():
    return {
        "model": MODEL,
        "answers": {"claim_0": answer()},
        "usage": {"input_tokens": 120, "output_tokens": 34},
    }


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


async def call(payload, *, request=REQUEST, status=200, calls=None, **options):
    calls = [] if calls is None else calls

    def transport(outgoing):
        calls.append(outgoing)
        content = payload if isinstance(payload, bytes) else encoded(payload)
        return httpx.Response(status, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client, **options)
        return await provider.decide(request)


async def test_native_http_shape_exact_context_synthetic_auth_and_usage(capfd):
    calls = []
    result = await call(response(), calls=calls, timeout_seconds=4.5)
    assert len(calls) == 1
    outgoing = calls[0]
    assert outgoing.method == "POST"
    assert str(outgoing.url) == "https://api.typesafe.ai/v1/systemone"
    assert outgoing.headers["authorization"] == f"Bearer {SECRET}"
    assert outgoing.headers["accept"] == outgoing.headers["content-type"] == "application/json"
    assert not any("long-context" in key or "preview" in key for key in outgoing.headers)
    assert json.loads(outgoing.content) == {
        "model": MODEL,
        "state": REQUEST.state,
        "questions": REQUEST.questions,
    }
    assert outgoing.extensions["timeout"] == dict.fromkeys(
        ("connect", "read", "write", "pool"), 4.5
    )
    assert result.model == MODEL
    assert result.usage == TokenUsage(120, 34, 0, True)
    choice = result.answers["claim_0"]
    assert choice.choice == "S" and choice.probabilities == answer()["probabilities"]
    assert choice.confidence == 0.85 and choice.derived_confidence == pytest.approx(0.85)
    assert choice.gate_score == pytest.approx(0.85) and choice.gate_score <= choice.confidence
    assert capfd.readouterr() == ("", "")  # Operation logs belong to the service.


@pytest.mark.parametrize("state", ["raw state", ["first", {"second": "中文"}], {}])
async def test_native_state_representations_and_multiple_questions(state):
    request = DecisionRequest(state, {"first": QUESTION, "second": QUESTION})
    data = response()
    data["answers"] = {"second": answer(), "first": answer()}
    result = await call(data, request=request)
    assert set(result.answers) == {"first", "second"}


@pytest.mark.parametrize(
    "confidence,maximum", [(0.8, 0.8533333333333333), (0.78, 0.8666666666666667)]
)
async def test_parser_tolerance_never_moves_either_score_over_threshold(confidence, maximum):
    data = response()
    data["answers"]["claim_0"].update(
        confidence=confidence,
        probabilities={"S": maximum, "C": (1 - maximum) / 2, "U": (1 - maximum) / 2},
    )
    choice = (await call(data)).answers["claim_0"]
    assert choice.gate_score < 0.8
    assert choice.confidence == confidence
    assert choice.probabilities["S"] == maximum


async def test_rounding_sum_and_tie_tolerances_do_not_renormalize():
    request = DecisionRequest(
        "context", {"claim_0": {"type": "choice", "criteria": {"a": None, "b": None}}}
    )
    data = response()
    data["answers"]["claim_0"] = {
        "type": "choice",
        "choice": "a",
        "confidence": 0.001,
        "probabilities": {"a": 0.5004996, "b": 0.5005004},
    }
    choice = (await call(data, request=request)).answers["claim_0"]
    assert choice.probabilities == data["answers"]["claim_0"]["probabilities"]
    assert choice.gate_score == 0.001


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", None),
        ("confidence", True),
        ("confidence", "0.85"),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("confidence", float("-inf")),
        ("confidence", 0.7),
        ("confidence", 0.82999999),
        ("confidence", 0.87000001),
        ("choice", "unknown"),
        ("choice", True),
        ("type", "noul"),
        ("probabilities", None),
        ("probabilities", {"S": 0.9, "C": 0.1}),
        ("probabilities", {"S": 0.9, "C": 0.05, "U": 0.04, "extra": 0.01}),
        ("probabilities", {"S": True, "C": 0, "U": 0}),
        ("probabilities", {"S": "0.9", "C": 0.05, "U": 0.05}),
        ("probabilities", {"S": float("nan"), "C": 0.05, "U": 0.05}),
        ("probabilities", {"S": float("inf"), "C": 0.05, "U": 0.05}),
        ("probabilities", {"S": 1.01, "C": 0, "U": -0.01}),
        ("probabilities", {"S": 0.9, "C": 0.05, "U": 0.04}),
        ("probabilities", {"S": 0.8, "C": 0.1, "U": 0.10101}),
        ("probabilities", {"S": 0.05, "C": 0.9, "U": 0.05}),
    ],
)
async def test_invalid_choices_fail_without_losing_measured_usage(field, value):
    data = response()
    data["answers"]["claim_0"][field] = value
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(data, calls=calls)
    error = caught.value
    assert error.code == "provider_protocol_error" and not error.retryable
    assert error.stats.usage == TokenUsage(120, 34, 0, True)
    assert error.stats.response_models == (MODEL,)
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["confidence", "choice", "type", "probabilities"])
async def test_missing_choice_fields_are_not_repaired(field):
    data = response()
    del data["answers"]["claim_0"][field]
    with pytest.raises(VerificationError, match="invalid response") as caught:
        await call(data)
    assert caught.value.stats.usage.complete


@pytest.mark.parametrize(
    "answers",
    [
        None,
        [],
        {},
        {"extra": answer()},
        {"claim_0": None},
        {"claim_0": answer(), "extra": answer()},
    ],
)
async def test_question_coverage_is_exact(answers):
    data = response()
    data["answers"] = answers
    with pytest.raises(VerificationError) as caught:
        await call(data)
    assert caught.value.code == "provider_protocol_error" and caught.value.stats.usage.complete


@pytest.mark.parametrize("model", [None, "jev-latest", "jev-1.13.0", "", 123, "\ud800"])
async def test_returned_model_must_match_pin_but_valid_identity_is_preserved(model):
    data = response()
    data["model"] = model
    # Escaped lone surrogates are valid JSON syntax but invalid model identifiers.
    payload = json.dumps(data).encode()
    with pytest.raises(VerificationError) as caught:
        await call(payload)
    assert caught.value.code == "provider_protocol_error"
    assert caught.value.stats.usage == TokenUsage(120, 34, 0, True)
    expected = (model,) if model in ("jev-latest", "jev-1.13.0") else ()
    assert caught.value.stats.response_models == expected


@pytest.mark.parametrize(
    "usage,expected",
    [
        (None, TokenUsage(complete=False)),
        ({}, TokenUsage(complete=False)),
        ({"input_tokens": 120}, TokenUsage(120, 0, 0, False)),
        ({"output_tokens": 34}, TokenUsage(0, 34, 0, False)),
        ({"input_tokens": True, "output_tokens": 34}, TokenUsage(0, 34, 0, False)),
        ({"input_tokens": -1, "output_tokens": 34}, TokenUsage(0, 34, 0, False)),
        ({"input_tokens": "120", "output_tokens": 34}, TokenUsage(0, 34, 0, False)),
        ({"input_tokens": 120, "output_tokens": 34.0}, TokenUsage(120, 0, 0, False)),
        ({"input_tokens": 120, "output_tokens": float("inf")}, TokenUsage(120, 0, 0, False)),
        ({"input_tokens": 0, "output_tokens": 0}, TokenUsage()),
    ],
)
async def test_missing_invalid_and_partial_native_usage_remains_honest(usage, expected):
    data = response()
    data["usage"] = usage
    assert (await call(data)).usage == expected
    data["answers"]["claim_0"]["confidence"] = None
    with pytest.raises(VerificationError) as caught:
        await call(data)
    assert caught.value.stats.usage == expected


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        b"null",
        b"true",
        b'{"answers":',
        b"\xff",
        b'{"model":"jev-1.14.0","model":"jev-1.13.0"}',
        b'{"answers":{"a":{},"a":{}}}',
        b'{"answers":{"a":{"probabilities":{"S":1,"S":0}}}}',
    ],
)
async def test_malformed_json_and_duplicate_keys_fail_safely(payload):
    with pytest.raises(VerificationError) as caught:
        await call(payload)
    assert caught.value.code == "provider_protocol_error"
    assert SECRET not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize(
    "original,replacement,usage,models",
    [
        (b'"choice":"S"', b'"choice":"C","choice":"S"', TokenUsage(317, 29), (MODEL,)),
        (b'"choice":"S"', b'"choice":"S","choice":"C"', TokenUsage(317, 29), (MODEL,)),
        (b'"choice":"S"', b'"choice":"S","\\u0063hoice":"S"', TokenUsage(317, 29), (MODEL,)),
        (b'"S":0.9', b'"S":0.1,"S":0.9', TokenUsage(317, 29), (MODEL,)),
        (b'"claim_0":{', b'"claim_0":null,"claim_0":{', TokenUsage(317, 29), (MODEL,)),
        (b'"answers":{', b'"answers":{},"answers":{', TokenUsage(317, 29), (MODEL,)),
        (
            b'"input_tokens":317',
            b'"input_tokens":999,"input_tokens":317',
            TokenUsage(0, 29, 0, False),
            (MODEL,),
        ),
        (
            b'"input_tokens":317',
            b'"input_tokens":999,"input_tokens":998,"input_tokens":317',
            TokenUsage(0, 29, 0, False),
            (MODEL,),
        ),
        (
            b'"input_tokens":317',
            b'"input_tokens":317,"input_tokens":317',
            TokenUsage(0, 29, 0, False),
            (MODEL,),
        ),
        (
            b'"input_tokens":317',
            b'"input_tokens":317,"\\u0069nput_tokens":317',
            TokenUsage(0, 29, 0, False),
            (MODEL,),
        ),
        (
            b'"output_tokens":29',
            b'"output_tokens":999,"output_tokens":29',
            TokenUsage(317, 0, 0, False),
            (MODEL,),
        ),
        (b'"usage":{', b'"usage":{},"usage":{', TokenUsage(complete=False), (MODEL,)),
        (
            b'"model":"jev-1.14.0"',
            b'"model":"jev-1.13.0","model":"jev-1.14.0"',
            TokenUsage(317, 29),
            (),
        ),
        (
            b'"model":"jev-1.14.0"',
            b'"model":"jev-1.14.0","model":"jev-1.14.0","model":"jev-1.14.0"',
            TokenUsage(317, 29),
            (),
        ),
        (
            b'"usage":{',
            b'"metadata":[{"ignored":1,"ignored":2}],"usage":{',
            TokenUsage(317, 29),
            (MODEL,),
        ),
        (
            b'"input_tokens":317',
            b'"ignored":{"key":1,"key":2},"input_tokens":317',
            TokenUsage(317, 29),
            (MODEL,),
        ),
    ],
    ids=[
        "choice-last-valid",
        "choice-first-valid",
        "choice-escaped-key",
        "probability",
        "question-id",
        "answers-container",
        "input-counter",
        "input-counter-three-values",
        "input-counter-identical",
        "input-counter-escaped-key",
        "output-counter",
        "usage-container",
        "model",
        "model-three-values",
        "ignored-object-in-list",
        "ignored-object-in-usage",
    ],
)
async def test_duplicate_keys_reject_response_but_retain_only_unambiguous_stats(
    original, replacement, usage, models, capfd
):
    data = response()
    data["usage"] = {"input_tokens": 317, "output_tokens": 29}
    payload = encoded(data)
    assert payload.count(original) == 1
    payload = payload.replace(original, replacement)
    stream = Chunks([payload[:17], payload[17:]])
    calls = []

    def transport(outgoing):
        calls.append(outgoing)
        return httpx.Response(200, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(VerificationError) as caught:
            await JevProvider(api_key=SECRET, client=client).decide(REQUEST)
        assert not client.is_closed
    error = caught.value
    assert error.code == "provider_protocol_error" and not error.retryable
    assert error.stats is not None
    assert error.stats.usage == usage and error.stats.response_models == models
    assert len(calls) == 1 and stream.closed
    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize("field", ["choice", "probability"])
async def test_duplicate_key_failure_stats_reach_actual_verifier_consumer(field, capfd):
    calls = []
    streams = []

    def transport(outgoing):
        calls.append(outgoing)
        questions = json.loads(outgoing.content)["questions"]
        answers = {}
        for question_id, question in questions.items():
            selected = next(iter(question["criteria"]))
            answers[question_id] = {
                "type": "choice",
                "choice": selected,
                "confidence": 1,
                "probabilities": {key: int(key == selected) for key in question["criteria"]},
            }
        payload = encoded(
            {
                "model": MODEL,
                "answers": answers,
                "usage": {"input_tokens": 317, "output_tokens": 29},
            }
        )
        first = next(iter(answers.values()))["choice"]
        token = encoded(first)
        original = b'"choice":' + token if field == "choice" else token + b":1"
        payload = payload.replace(original, original + b"," + original, 1)
        stream = Chunks([payload])
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client)
        verifier = build_verifier(
            "jev_minimal",
            decision_provider=provider,
            settings=Settings(approach="jev_minimal", jev_fallback=False, diagnostics=True),
        )
        with pytest.raises(VerificationError) as caught:
            await verifier.verify_claims(["Cedar resumes at one."], ["Cedar resumes at one."])
        await verifier.aclose()
        assert not client.is_closed
    error = caught.value
    assert error.code == "provider_protocol_error" and not error.retryable
    assert error.stats.usage == TokenUsage(317, 29)
    assert error.stats.response_models == (MODEL,) and error.stats.provider_calls == 1
    assert error.stats.retries == error.stats.repairs == 0
    assert len(error.stats.attempts) == 1
    attempt = error.stats.attempts[0]
    assert attempt.stage == "jev_judgment" and attempt.error_code == error.code
    assert attempt.usage == TokenUsage(317, 29) and attempt.response_models == (MODEL,)
    assert attempt.question_count == len(json.loads(calls[0].content)["questions"])
    assert len(calls) == 1 and all(stream.closed for stream in streams)
    captured = capfd.readouterr()
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert any(
        r["stage"] == "jev_judgment"
        and r["outcome"] == "failure"
        and r.get("error_code") == error.code
        for r in records
    )
    assert records[-1]["event"] == "end" and records[-1]["error_code"] == error.code
    assert len({r["request_id"] for r in records}) == 1
    assert SECRET not in captured.out + captured.err and "Cedar" not in captured.err


@pytest.mark.parametrize(
    "candidate_request",
    [
        DecisionRequest(None, {"q": QUESTION}),
        DecisionRequest(123, {"q": QUESTION}),
        DecisionRequest("state", {}),
        DecisionRequest("state", {"": QUESTION}),
        DecisionRequest("state", {1: QUESTION}),
        DecisionRequest("state", {"q": None}),
        DecisionRequest("state", {"q": {"type": "noul", "criteria": {"a": None, "b": None}}}),
        DecisionRequest("state", {"q": {"type": "choice", "criteria": {"a": None}}}),
        DecisionRequest("state", {"q": {"type": "choice", "criteria": {"": None, "b": None}}}),
        DecisionRequest("state", {"q": {"type": "choice", "criteria": {"a": True, "b": None}}}),
        DecisionRequest(
            "state", {"q": {"type": "choice", "criteria": {str(i): None for i in range(256)}}}
        ),
        DecisionRequest({"bad": float("nan")}, {"q": QUESTION}),
        DecisionRequest({"bad": object()}, {"q": QUESTION}),
        DecisionRequest({1: "ambiguous key"}, {"q": QUESTION}),
        DecisionRequest("\ud800", {"q": QUESTION}),
    ],
)
async def test_invalid_request_is_rejected_before_any_http_attempt(candidate_request):
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(response(), request=candidate_request, calls=calls)
    assert caught.value.code == "invalid_request" and not calls


async def test_request_and_state_plus_single_question_limits_are_exact_utf8_bytes():
    body = {"model": MODEL, "state": REQUEST.state, "questions": REQUEST.questions}
    size = len(encoded(body))
    calls = []
    await call(response(), calls=calls, max_request_bytes=size, max_question_bytes=size)
    assert calls[0].content == encoded(body)
    for options in (
        {"max_request_bytes": size - 1, "max_question_bytes": size - 1},
        {"max_request_bytes": size, "max_question_bytes": size - 1},
    ):
        calls = []
        with pytest.raises(VerificationError) as caught:
            await call(response(), calls=calls, **options)
        assert caught.value.code == "unsupported_capability" and not calls


async def test_question_limit_includes_shared_state_not_only_instructions():
    request = DecisionRequest("中" * 400, {"claim_0": QUESTION, "other": QUESTION})
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(response(), request=request, calls=calls, max_question_bytes=1000)
    assert caught.value.code == "unsupported_capability" and not calls


@pytest.mark.parametrize("key", [None, "", "  ", "bad\nkey", "bad key", "非ASCII"])
async def test_missing_or_invalid_key_never_reaches_http(key):
    calls = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as client:
        provider = JevProvider(api_key=key, client=client)
        with pytest.raises(VerificationError) as caught:
            await provider.decide(REQUEST)
    assert caught.value.code == "not_configured" and not calls


@pytest.mark.parametrize(
    "options",
    [
        {"model": "jev-latest"},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"max_request_bytes": 0},
        {"max_question_bytes": True},
        {"max_request_bytes": 1, "max_question_bytes": 2},
    ],
)
async def test_bad_provider_configuration_is_safe(options):
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(response(), calls=calls, **options)
    assert caught.value.code == "not_configured" and not calls


@pytest.mark.parametrize(
    "status,code",
    [
        (301, "provider_protocol_error"),
        (400, "provider_protocol_error"),
        (401, "authentication_failed"),
        (403, "authentication_failed"),
        (404, "provider_protocol_error"),
        (408, "upstream_timeout"),
        (413, "unsupported_capability"),
        (422, "provider_protocol_error"),
        (429, "rate_limited"),
        (500, "upstream_unavailable"),
        (504, "upstream_timeout"),
    ],
)
async def test_http_errors_are_classified_without_body_or_hidden_retry(status, code, capfd):
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(SECRET.encode(), status=status, calls=calls)
    assert caught.value.code == code and len(calls) == 1
    assert SECRET not in str(caught.value) + repr(caught.value)
    assert capfd.readouterr() == ("", "")


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks=(), *, failure=None, waiting=None):
        self.chunks = chunks
        self.failure = failure
        self.waiting = waiting
        self.closed = False
        self.iterated = False

    async def __aiter__(self):
        self.iterated = True
        for chunk in self.chunks:
            yield chunk
        if self.failure:
            raise self.failure
        if self.waiting:
            self.waiting.set()
            await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


async def test_http_error_body_is_never_read_and_stream_still_closes():
    stream = Chunks([SECRET.encode()], failure=AssertionError("error_body_must_not_be_read"))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(429, stream=stream))
    ) as client:
        with pytest.raises(VerificationError) as caught:
            await JevProvider(api_key=SECRET, client=client).decide(REQUEST)
    assert caught.value.code == "rate_limited" and stream.closed and not stream.iterated


async def test_custom_base_url_and_native_key_whitespace_handling():
    calls = []

    def transport(outgoing):
        calls.append(outgoing)
        return httpx.Response(200, content=encoded(response()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await JevProvider(
            api_key="  " + SECRET + "  ", base_url="http://fixture.invalid/v1/", client=client
        ).decide(REQUEST)
    assert result.model == MODEL and len(calls) == 1
    assert str(calls[0].url) == "http://fixture.invalid/v1/systemone"
    assert calls[0].headers["authorization"] == f"Bearer {SECRET}"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://fixture.invalid",
        "https://user:password@fixture.invalid",
        "https://fixture.invalid?key=secret",
        "https://fixture.invalid#secret",
        "",
        None,
    ],
)
async def test_invalid_or_credential_bearing_base_url_never_reaches_http(base_url):
    calls = []
    with pytest.raises(VerificationError) as caught:
        await call(response(), calls=calls, base_url=base_url)
    assert caught.value.code == "not_configured" and not calls


@pytest.mark.parametrize(
    "failure,code",
    [
        (httpx.ReadTimeout(SECRET), "upstream_timeout"),
        (httpx.ReadError(SECRET), "upstream_unavailable"),
        (httpx.RemoteProtocolError(SECRET), "upstream_unavailable"),
        (httpx.DecodingError(SECRET), "provider_protocol_error"),
    ],
)
async def test_read_failure_closes_stream_and_preserves_safe_error(failure, code):
    stream = Chunks([b'{"answers":'], failure=failure)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=stream))
    ) as client:
        with pytest.raises(VerificationError) as caught:
            await JevProvider(api_key=SECRET, client=client).decide(REQUEST)
    assert caught.value.code == code and stream.closed
    assert SECRET not in str(caught.value)


async def test_response_limit_exact_boundary_and_one_byte_over():
    payload = encoded(response())
    for extra, expected in ((0, None), (1, "response_too_large")):
        stream = Chunks([payload, b" " * (MAX_RESPONSE_BYTES - len(payload)), b" " * extra])
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=stream))
        ) as client:
            provider = JevProvider(api_key=SECRET, client=client)
            if expected:
                with pytest.raises(VerificationError) as caught:
                    await provider.decide(REQUEST)
                assert caught.value.code == expected
            else:
                assert (await provider.decide(REQUEST)).usage.complete
        assert stream.closed


async def test_cancellation_closes_stream_and_next_request_recovers():
    waiting = asyncio.Event()
    stream = Chunks([b'{"model":'], waiting=waiting)
    calls = []

    def transport(outgoing):
        calls.append(outgoing)
        return (
            httpx.Response(200, stream=stream)
            if len(calls) == 1
            else httpx.Response(200, content=encoded(response()))
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client)
        task = asyncio.create_task(provider.decide(REQUEST))
        await asyncio.wait_for(waiting.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed
        assert (await provider.decide(REQUEST)).model == MODEL
        await provider.aclose()
        assert not client.is_closed
    assert len(calls) == 2


async def test_secret_seeded_connection_failure_has_no_output_and_recovers(capfd):
    calls = []

    def transport(outgoing):
        calls.append(outgoing)
        if len(calls) == 1:
            error = type(SECRET, (httpx.ConnectError,), {})(SECRET)
            error.add_note(SECRET)
            exec(
                compile("raise error", SECRET + ".py", "exec"),
                {"error": error, "local_secret": SECRET},
            )
        return httpx.Response(200, content=encoded(response()))

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client)
        assert SECRET not in repr(provider)
        with pytest.raises(VerificationError) as caught:
            await provider.decide(DecisionRequest(SECRET, {"claim_0": QUESTION}))
        assert caught.value.code == "upstream_unavailable"
        assert (await provider.decide(REQUEST)).model == MODEL
    assert len(calls) == 2 and capfd.readouterr() == ("", "")


async def test_injected_client_redirects_and_auth_do_not_add_attempts():
    calls = []

    def transport(request):
        calls.append(request)
        return httpx.Response(307, headers={"location": "https://other.invalid/secret"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), follow_redirects=True, auth=("other", SECRET)
    ) as client:
        with pytest.raises(VerificationError):
            await JevProvider(api_key=SECRET, client=client).decide(REQUEST)
    assert len(calls) == 1 and calls[0].headers["authorization"] == f"Bearer {SECRET}"


async def test_owned_client_closes():
    provider = JevProvider(api_key=SECRET)
    assert not provider._client.is_closed
    await provider.aclose()
    assert provider._client.is_closed


async def test_request_inputs_are_not_mutated():
    request = copy.deepcopy(REQUEST)
    await call(response(), request=request)
    assert request == REQUEST
