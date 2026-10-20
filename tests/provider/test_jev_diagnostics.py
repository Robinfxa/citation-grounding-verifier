from __future__ import annotations

import json

import httpx
import pytest

from grounding import diagnostics
from grounding.config import Settings
from grounding.contracts import DecisionRequest, TokenUsage, VerificationError
from grounding.jev_provider import JevProvider
from grounding.verifiers import build_verifier

MODEL = "jev-1.14.0"
SECRET = "JEV_DIAGNOSTIC_SYNTHETIC_SECRET"
SELECTED = SECRET + "_CHOICE"
QUESTION_ID = SECRET + '_QUESTION\n{"forged":true}'
REASONS = (
    "duplicate_json_key",
    "returned_model",
    "answer_coverage",
    "answer_type",
    "choice_not_declared",
    "confidence_invalid",
    "probability_keys",
    "probability_invalid",
    "probability_sum",
    "choice_not_argmax",
    "confidence_formula",
)
ALLOWED = {
    "request_id",
    "stage",
    "event",
    "outcome",
    "elapsed_ms",
    "error_code",
    "protocol_reason",
    "provider_calls",
    "retries",
    "repairs",
    "claims",
    "routing_reason",
}


def request():
    return DecisionRequest(
        {"context": SECRET},
        {
            QUESTION_ID: {
                "type": "choice",
                "instructions": SECRET,
                "criteria": {SELECTED: SECRET, "C": None, "U": None},
            }
        },
    )


def response_for(candidate):
    answers = {}
    for key, question in candidate.questions.items():
        selected = next(iter(question["criteria"]))
        answers[key] = {
            "type": "choice",
            "choice": selected,
            "confidence": 1,
            "probabilities": {option: int(option == selected) for option in question["criteria"]},
        }
    return {
        "model": MODEL,
        "answers": answers,
        "usage": {"input_tokens": 317, "output_tokens": 29},
        "metadata": {"untrusted": SECRET + '\n{"forged":true}'},
    }


def encode(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()


def invalid_payload(reason):
    data = response_for(request())
    answer = data["answers"][QUESTION_ID]
    if reason == "duplicate_json_key":
        raw = encode(data)
        token = b'"choice":' + encode(SELECTED)
        assert raw.count(token) == 1
        return raw.replace(token, token + b"," + token, 1)
    if reason == "returned_model":
        data["model"] = "jev-1.13.0"
    elif reason == "answer_coverage":
        data["answers"] = {}
    elif reason == "answer_type":
        answer["type"] = SECRET
    elif reason == "choice_not_declared":
        answer["choice"] = SECRET + "_UNKNOWN\n{}"
    elif reason == "confidence_invalid":
        answer["confidence"] = SECRET
    elif reason == "probability_keys":
        answer["probabilities"].pop("U")
    elif reason == "probability_invalid":
        answer["probabilities"][SELECTED] = SECRET
    elif reason == "probability_sum":
        answer["probabilities"] = {SELECTED: 0.5, "C": 0, "U": 0}
    elif reason == "choice_not_argmax":
        answer["choice"] = "C"
    elif reason == "confidence_formula":
        answer["confidence"] = 0.2
    else:
        raise AssertionError("unknown synthetic case")
    return encode(data)


class Body(httpx.AsyncByteStream):
    def __init__(self, raw):
        self.raw = raw
        self.closed = False

    async def __aiter__(self):
        yield self.raw[:13]
        yield self.raw[13:]

    async def aclose(self):
        self.closed = True


async def native_call(payload, calls, streams):
    def transport(outgoing):
        calls.append(outgoing)
        stream = Body(payload)
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client)
        try:
            return await provider.decide(request())
        finally:
            await provider.aclose()
            assert not client.is_closed


def records(raw):
    assert SECRET not in raw and "forged" not in raw and "Cedar" not in raw
    parsed = [json.loads(line) for line in raw.splitlines()]
    for record in parsed:
        assert set(record) <= ALLOWED
        assert len(record["request_id"]) == 32
        assert type(record["elapsed_ms"]) in (int, float) and record["elapsed_ms"] >= 0
        assert len(encode(record)) < 512
    return parsed


@pytest.mark.parametrize("reason", REASONS)
async def test_native_guard_reasons_are_distinct_and_preserve_safe_error_and_usage(reason, capfd):
    calls, streams = [], []
    with diagnostics.operation(enabled=True, new=True) as operation:
        with pytest.raises(VerificationError) as caught:
            await native_call(invalid_payload(reason), calls, streams)
    error = caught.value
    assert error.code == "provider_protocol_error" and not error.retryable
    assert error.stats.usage == TokenUsage(317, 29)
    expected_model = "jev-1.13.0" if reason == "returned_model" else MODEL
    assert error.stats.response_models == (expected_model,)
    assert error.stats.provider_calls == 1 and error.stats.retries == error.stats.repairs == 0
    assert SECRET not in str(error) + repr(error)
    assert len(calls) == 1 and len(streams) == 1 and streams[0].closed
    captured = capfd.readouterr()
    assert captured.out == ""
    emitted = records(captured.err)
    assert len(emitted) == 1
    assert emitted[0] == {
        "request_id": operation.request_id,
        "stage": "jev_decision",
        "event": "validation",
        "outcome": "failure",
        "error_code": "provider_protocol_error",
        "protocol_reason": reason,
        "elapsed_ms": emitted[0]["elapsed_ms"],
    }


async def test_only_first_guard_is_logged_for_one_response(capfd):
    data = json.loads(invalid_payload("confidence_invalid"))
    data["answers"][QUESTION_ID]["probabilities"] = {}
    with diagnostics.operation(enabled=True, new=True):
        with pytest.raises(VerificationError):
            await native_call(encode(data), [], [])
    emitted = records(capfd.readouterr().err)
    assert [item.get("protocol_reason") for item in emitted] == ["confidence_invalid"]


@pytest.mark.parametrize(
    "unknown",
    [
        "unknown",
        SECRET + '\n{"forged":true}',
        "confidence_invalid ",
        pytest.param([SECRET], id="list"),
        pytest.param({"untrusted": SECRET}, id="dict"),
    ],
)
def test_unknown_protocol_reason_is_discarded(unknown, capfd):
    with diagnostics.operation(enabled=True, new=True):
        diagnostics.emit(
            "jev_decision",
            "validation",
            "failure",
            error_code="provider_protocol_error",
            protocol_reason=unknown,
        )
    emitted = records(capfd.readouterr().err)
    assert len(emitted) == 1 and "protocol_reason" not in emitted[0]


@pytest.mark.parametrize("enabled", [False, True])
async def test_diagnostics_opt_in_preserves_failure_and_usage(enabled, capfd):
    with diagnostics.operation(enabled=enabled, new=True):
        with pytest.raises(VerificationError) as caught:
            await native_call(invalid_payload("confidence_formula"), [], [])
    assert caught.value.code == "provider_protocol_error"
    assert caught.value.stats.usage == TokenUsage(317, 29)
    raw = capfd.readouterr().err
    if enabled:
        assert [item.get("protocol_reason") for item in records(raw)] == ["confidence_formula"]
    else:
        assert raw == ""


async def test_native_without_operation_remains_silent(capfd):
    with pytest.raises(VerificationError) as caught:
        await native_call(invalid_payload("confidence_invalid"), [], [])
    assert caught.value.code == "provider_protocol_error"
    assert capfd.readouterr() == ("", "")


async def test_actual_library_consumer_success_failures_and_recovery(capfd):
    mode = "success"
    calls, streams = [], []

    def transport(outgoing):
        calls.append(outgoing)
        if mode == "transport_failure":
            error = httpx.ConnectError(SECRET + '\n{"forged":true}')
            error.add_note(SECRET + "_NOTE")
            raise error
        body = json.loads(outgoing.content)
        candidate = DecisionRequest(body["state"], body["questions"])
        data = response_for(candidate)
        first = next(iter(data["answers"].values()))
        if mode == "confidence_invalid":
            first["confidence"] = SECRET
        elif mode == "probability_sum":
            first["probabilities"] = {key: 0 for key in first["probabilities"]}
        stream = Body(encode(data))
        streams.append(stream)
        return httpx.Response(200, stream=stream)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider = JevProvider(api_key=SECRET, client=client)
        verifier = build_verifier(
            "jev_minimal",
            decision_provider=provider,
            settings=Settings(
                approach="jev_minimal",
                jev_fallback=False,
                diagnostics=True,
                transport_retries=0,
                retry_delay=0,
            ),
        )
        for mode in (
            "success",
            "confidence_invalid",
            "probability_sum",
            "transport_failure",
            "success",
        ):
            before = len(calls)
            if mode == "success":
                run = await verifier.verify_claims(
                    ["Cedar resumes at one. " + SECRET], ["Cedar resumes at one."]
                )
                assert run.report.claims[0].verdict == "SUPPORTED"
                assert run.report.claims[0].citations[0].quote in "Cedar resumes at one. " + SECRET
                assert run.stats.provider_calls == 2 and run.stats.usage == TokenUsage(634, 58)
            else:
                with pytest.raises(VerificationError) as caught:
                    await verifier.verify_claims(
                        ["Cedar resumes at one. " + SECRET], ["Cedar resumes at one."]
                    )
                error = caught.value
                expected = (
                    "upstream_unavailable"
                    if mode == "transport_failure"
                    else "provider_protocol_error"
                )
                assert error.code == expected
                expected_usage = (
                    TokenUsage(complete=False)
                    if mode == "transport_failure"
                    else TokenUsage(317, 29)
                )
                assert error.stats.usage == expected_usage
                assert error.stats.provider_calls == 1
                assert error.stats.retries == error.stats.repairs == 0
                assert error.stats.attempts[0].error_code == expected
                assert error.stats.attempts[0].usage == expected_usage
            assert len(calls) - before == (2 if mode == "success" else 1)
            assert all(stream.closed for stream in streams)
            captured = capfd.readouterr()
            assert captured.out == ""
            emitted = records(captured.err)
            assert len({item["request_id"] for item in emitted}) == 1
            assert emitted[0]["event"] == "start" and emitted[-1]["event"] == "end"
            assert emitted[-1]["outcome"] == ("success" if mode == "success" else "failure")
            reasons = [item["protocol_reason"] for item in emitted if "protocol_reason" in item]
            assert reasons == ([mode] if mode in {"confidence_invalid", "probability_sum"} else [])
        await verifier.aclose()
        assert not client.is_closed


@pytest.mark.parametrize("valid", [False, True])
async def test_broken_sink_does_not_change_native_result_or_protocol_error(
    valid, monkeypatch, capfd
):
    writes = []

    def broken_write(fd, raw):
        writes.append((fd, raw))
        error = OSError(SECRET + '\n{"forged":true}')
        error.add_note(SECRET + "_NOTE")
        raise error

    monkeypatch.setattr(diagnostics.os, "write", broken_write)
    calls, streams = [], []
    with diagnostics.operation(enabled=True, new=True):
        if valid:
            result = await native_call(encode(response_for(request())), calls, streams)
            assert result.usage == TokenUsage(317, 29)
        else:
            with pytest.raises(VerificationError) as caught:
                await native_call(invalid_payload("confidence_invalid"), calls, streams)
            assert caught.value.code == "provider_protocol_error"
            assert caught.value.stats.usage == TokenUsage(317, 29)
    assert len(calls) == 1 and all(stream.closed for stream in streams)
    assert len(writes) == (0 if valid else 1)
    assert capfd.readouterr() == ("", "")
    if writes:
        assert writes[0][0] == 2
        assert records(writes[0][1].decode())[0]["protocol_reason"] == "confidence_invalid"
