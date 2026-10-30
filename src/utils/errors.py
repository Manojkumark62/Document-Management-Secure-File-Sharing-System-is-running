import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class RateLimitExceeded(StarletteHTTPException):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            status_code=429,
            detail=(
                "Login temporarily paused after too many attempts. "
                f"Please wait {retry_after_seconds} seconds before trying again."
            ),
            headers={"Retry-After": str(retry_after_seconds)},
        )


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "details": details},
            "request_id": getattr(request.state, "request_id", None),
        },
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "warning": {
                    "code": "login_rate_limit_exceeded",
                    "message": exc.detail,
                    "retry_after_seconds": exc.retry_after_seconds,
                },
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=exc.headers,
        )

    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    details = None if isinstance(exc.detail, str) else exc.detail
    return _error_response(
        request,
        exc.status_code,
        f"http_{exc.status_code}",
        message,
        details,
        exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return _error_response(
        request,
        422,
        "validation_error",
        "Request validation failed",
        details,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled request error", extra={"request_id": request_id})
    return _error_response(
        request,
        500,
        "internal_server_error",
        "An unexpected error occurred",
    )
