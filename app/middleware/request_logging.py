"""Logs one structured line per HTTP request: method, path, status, duration.

NestJS comparison: a middleware/`LoggingInterceptor`. FastAPI middleware wraps
EVERY request, including 404s and validation errors that never reach a route.

Deliberately NOT logged: headers (contain `Authorization: Bearer ...`), query
strings, and bodies (may contain passwords). Request IDs come in Phase 6.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

logger = logging.getLogger("app.request")


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # perf_counter is a monotonic clock: right for measuring durations
    # (time.time() can jump if the system clock changes).
    start = time.perf_counter()
    try:
        # `await call_next` hands the request to the rest of the app and
        # waits (without blocking other requests) for the response.
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        raise

    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,  # path only: no query string
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )
    return response
