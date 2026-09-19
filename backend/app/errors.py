"""统一错误响应包络：所有面向前端的错误均返回同一形状。

    {"error": {"code": "<稳定错误码>", "message": "<可读信息>", "details": {...}}}

约定：
- HTTP 404 -> code "not_found"（资源不存在，details.resource 指明资源）
- HTTP 409 业务冲突：
    - "seats_unavailable"  空座不足（details.reason: "seats_unavailable"）
    - "seat_overlap"       与既有持座重叠（details.reason: "seat_overlap"）
- HTTP 422 -> code "validation_error"（请求参数不合法）
- HTTP 500 -> code "internal_error"（兜底，避免框架默认 HTML/裸字符串）
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


# 稳定错误码
NOT_FOUND = "not_found"
SEATS_UNAVAILABLE = "seats_unavailable"
SEAT_OVERLAP = "seat_overlap"
VALIDATION_ERROR = "validation_error"
INTERNAL_ERROR = "internal_error"


class ApiError(Exception):
    """携带稳定 code / message / details 的业务错误。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def not_found(resource: str, message: str, **details: Any) -> ApiError:
    return ApiError(404, NOT_FOUND, message, {"resource": resource, **details})


def seats_unavailable(
    message: str,
    *,
    showtime_id: int,
    party_size: int,
    preferred_row: int | None = None,
) -> ApiError:
    return ApiError(
        409,
        SEATS_UNAVAILABLE,
        message,
        {
            "reason": SEATS_UNAVAILABLE,
            "showtime_id": showtime_id,
            "party_size": party_size,
            "preferred_row": preferred_row,
        },
    )


def seat_overlap(
    message: str,
    *,
    showtime_id: int,
    party_size: int,
    conflicting_holds: list[dict[str, Any]] | None = None,
) -> ApiError:
    return ApiError(
        409,
        SEAT_OVERLAP,
        message,
        {
            "reason": "seat_overlap",
            "showtime_id": showtime_id,
            "party_size": party_size,
            "conflicting_holds": conflicting_holds or [],
        },
    )


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
    )


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """把直接抛出的 HTTPException（含路由未命中的 404）规整成包络形状。

    FastAPI.HTTPException 是 StarletteHTTPException 子类，detail 为裸字符串时
    原先直接透出，这里统一包络。
    """
    code = {
        404: NOT_FOUND,
        409: "conflict",
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
    }.get(exc.status_code, "error")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, detail),
    )


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            VALIDATION_ERROR,
            "请求参数不合法",
            {"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """兜底：未预期错误也返回 JSON 包络，而非框架默认 500 HTML。"""
    return JSONResponse(
        status_code=500,
        content=error_body(INTERNAL_ERROR, "服务器内部错误"),
    )


def register_error_handlers(app) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    # StarletteHTTPException 须单独注册：路由未命中的 404 由 Starlette 直接抛出，
    # FastAPI.HTTPException 是其子类，注册基类处理器即可同时兜住两者。
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
