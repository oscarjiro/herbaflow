"""RFC 9457 application/problem+json error mapping (one shape for all errors)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("herbaflow.errors")

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemException(Exception):
    """An error carrying an RFC 9457 problem document."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        type_: str = "about:blank",
        **extra: Any,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_
        self.extra = extra
        super().__init__(detail or title)


class NotFoundProblem(ProblemException):
    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(404, "Not Found", detail, **extra)


class GoneProblem(ProblemException):
    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(410, "Gone", detail, **extra)


class ConflictProblem(ProblemException):
    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(409, "Conflict", detail, **extra)


class ValidationProblem(ProblemException):
    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(422, "Unprocessable Entity", detail, **extra)


def _problem(status: int, title: str, detail: str | None, type_: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE)


async def _problem_handler(request: Request, exc: ProblemException) -> JSONResponse:
    return _problem(exc.status, exc.title, exc.detail, exc.type_, **exc.extra)


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem(
        422,
        "Unprocessable Entity",
        "Request validation failed.",
        "about:blank",
        errors=exc.errors(),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return _problem(500, "Internal Server Error", "An internal error occurred.", "about:blank")


def register_error_handlers(app: FastAPI) -> None:
    """Wire the problem+json handlers onto the app."""
    app.add_exception_handler(ProblemException, _problem_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
