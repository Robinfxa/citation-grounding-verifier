"""HTTP consumer with bounded bodies, safe errors, deadlines and disconnect cancellation."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from grounding import diagnostics
from grounding.config import Settings
from grounding.contracts import (
    MAX_BODY_BYTES,
    InvalidReport,
    VerificationError,
    VerificationReport,
    Verifier,
    VerifyRequest,
    validate_report,
)
from grounding.verifiers import build_verifier


def _error_response(error: VerificationError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {
            "code": error.code, "message": error.message, "request_id": diagnostics.request_id(),
        }},
    )


class _ClientDisconnected(Exception):
    pass


class _RequestBoundary:
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with diagnostics.operation(enabled=self.settings.diagnostics, new=True) as operation:
            scope.setdefault("state", {})
            diagnostics.emit("http", "start", "started")
            status = 500
            response_started = False

            async def observed_send(message: Message) -> None:
                nonlocal status, response_started
                if message["type"] == "http.response.start":
                    status = message["status"]
                    response_started = True
                    message = {**message, "headers": [
                        (key, value) for key, value in message.get("headers", [])
                        if key.lower() != b"x-request-id"
                    ] + [(b"x-request-id", operation.request_id.encode("ascii"))]}
                await send(message)

            try:
                async with asyncio.timeout(self.settings.operation_timeout):
                    body = await self._body(scope, receive)
                    await self._dispatch(scope, body, receive, observed_send)
            except (_ClientDisconnected, asyncio.CancelledError) as error:
                diagnostics.emit("http", "end", "cancelled")
                if isinstance(error, asyncio.CancelledError):
                    raise
                return
            except Exception as error:
                if isinstance(error, TimeoutError):
                    error = VerificationError("deadline_exceeded")
                elif not isinstance(error, VerificationError):
                    error = VerificationError("internal_error")
                scope["state"]["error_code"] = error.code
                if not response_started:
                    await _error_response(error)(scope, receive, observed_send)
            diagnostics.emit(
                "http", "end", "success" if status < 400 else "failure",
                error_code=scope["state"].get("error_code"),
            )

    async def _body(self, scope: Scope, receive: Receive) -> bytes:
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    raise VerificationError("invalid_request") from None
                if length < 0:
                    raise VerificationError("invalid_request")
                if length > MAX_BODY_BYTES:
                    raise VerificationError("body_too_large")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise _ClientDisconnected
            if message["type"] != "http.request":
                raise VerificationError("invalid_request")
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                raise VerificationError("body_too_large")
            body.extend(chunk)
            if not message.get("more_body", False):
                return bytes(body)

    async def _dispatch(self, scope: Scope, body: bytes, receive: Receive, send: Send) -> None:
        delivered = False
        disconnected = asyncio.Event()

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def watch_disconnect() -> None:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    disconnected.set()
                    return

        # AIDEV-NOTE: cancelling only the HTTP waiter would leave model work running.
        # Both deadline and client disconnect cancel and join the same request task.
        request_task = asyncio.create_task(self.app(scope, replay, send))
        disconnect_task = asyncio.create_task(watch_disconnect())
        try:
            done, _ = await asyncio.wait(
                (request_task, disconnect_task), return_when=asyncio.FIRST_COMPLETED
            )
            if request_task in done:
                await request_task
            else:
                raise _ClientDisconnected
        finally:
            for task in (request_task, disconnect_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(request_task, disconnect_task, return_exceptions=True)


def create_app(*, verifier: Verifier | None = None, settings: Settings | None = None) -> FastAPI:
    config_error = None
    if settings is None:
        try:
            settings = Settings.from_env()
        except VerificationError as error:
            config_error = error
            settings = Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            if application.state.verifier is not None:
                await application.state.verifier.aclose()

    application = FastAPI(title="Citation Grounding Verifier", lifespan=lifespan)
    application.state.verifier = verifier
    application.state.settings = settings
    application.add_middleware(_RequestBoundary, settings=settings)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError) -> JSONResponse:
        request.state.error_code = "invalid_request"
        diagnostics.emit("http", "validation", "failure", error_code="invalid_request")
        return _error_response(VerificationError("invalid_request"))

    @application.exception_handler(VerificationError)
    async def verification_error(request: Request, error: VerificationError) -> JSONResponse:
        request.state.error_code = error.code
        return _error_response(error)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        if error.status_code in (400, 422):
            request.state.error_code = "invalid_request"
            diagnostics.emit("http", "validation", "failure", error_code="invalid_request")
            return _error_response(VerificationError("invalid_request"))
        if error.status_code in (404, 405):
            return JSONResponse(
                {"detail": "Not Found" if error.status_code == 404 else "Method Not Allowed"},
                status_code=error.status_code,
            )
        request.state.error_code = "internal_error"
        return _error_response(VerificationError("internal_error"))

    @application.post("/verify", response_model=VerificationReport)
    async def verify(body: VerifyRequest) -> VerificationReport:
        if not body.generated_answer.strip():
            return VerificationReport(claims=[])
        if config_error:
            raise config_error
        if application.state.verifier is None:
            application.state.verifier = build_verifier(settings.approach, settings=settings)
        run = await application.state.verifier.verify(body)
        try:
            report = VerificationReport.model_validate(run.report.model_dump())
            return validate_report(report, body.context_passages)
        except (ValidationError, InvalidReport):
            raise VerificationError("invalid_model_output") from None

    return application


app = create_app()
