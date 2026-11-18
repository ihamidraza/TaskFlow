"""Application errors and the handlers that turn them into HTTP responses.

Services raise these (e.g. `raise ConflictError(...)`), never `HTTPException`.
That keeps business logic free of HTTP details: the same service could run from
a CLI or a background job. One handler translates every AppError into the
spec's error format:

    {"error": {"code": "EMAIL_ALREADY_REGISTERED", "message": "...", "details": null}}

NestJS comparison: custom exceptions + a global `@Catch()` ExceptionFilter.
(`request_id` is added to this body in Phase 6.)
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class AppError(Exception):
    """Base class. Subclasses set the default HTTP status, code and message."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self, message: str | None = None, *, code: str | None = None, details: Any = None
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "INVALID_OPERATION"
    message = "The operation is not allowed"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_FAILED"
    message = "Could not validate credentials"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"
    message = "You don't have permission to perform this action"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state"


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Shape of every error body. Used to document error responses in /docs."""

    error: ErrorInfo


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Build the `responses=` argument for a route, e.g. error_responses(401, 409)."""
    return {code: {"model": ErrorResponse} for code in status_codes}


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    headers = None
    if isinstance(exc, AuthenticationError):
        # RFC 6750: a 401 for bearer auth should say which scheme to use.
        headers = {"WWW-Authenticate": "Bearer"}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.details),
        headers=headers,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Replace FastAPI's default 422 body.

    The default echoes each invalid value back in an `input` field, so a
    rejected password would be copied into the response (and into any proxy or
    client log that records it). We keep only where and why.
    """
    assert isinstance(exc, RequestValidationError)
    details = [
        {"loc": list(err["loc"]), "message": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Request validation failed", details),
    )


def register_exception_handlers(app: FastAPI) -> None:
    # A handler registered for a base class also catches all its subclasses.
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
