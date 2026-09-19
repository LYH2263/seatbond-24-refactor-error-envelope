"""Stable error envelope: every error response is JSON ``{code, message, details?}``.

``code`` is a stable machine-readable string; ``message`` is human-readable;
``details`` optionally carries structured context (e.g. a ``reason`` key for
409 conflicts telling insufficient-seats apart from overlap).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorCode:
    """Stable, machine-distinguishable error codes."""

    # 404 — resource does not exist
    SHOWTIME_NOT_FOUND = "SHOWTIME_NOT_FOUND"
    # 409 — business conflicts
    INSUFFICIENT_CONTIGUOUS_SEATS = "INSUFFICIENT_CONTIGUOUS_SEATS"
    HOLD_OVERLAP = "HOLD_OVERLAP"
    # generic fallbacks
    VALIDATION_ERROR = "VALIDATION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiError(Exception):
    """Raise from endpoints to emit the error envelope with a stable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _envelope(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorEnvelope(code=code, message=message, details=details)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body.model_dump(exclude_none=True)),
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _envelope(exc.status_code, ErrorCode.HTTP_ERROR, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _envelope(
            422,
            ErrorCode.VALIDATION_ERROR,
            "请求参数不合法",
            {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(_request: Request, exc: Exception) -> JSONResponse:
        return _envelope(500, ErrorCode.INTERNAL_ERROR, "服务器内部错误")
