"""Liveness and readiness probes (unversioned, per the spec).

/health/live   "Is the process up?"  Never touches dependencies. If this fails,
               an orchestrator (Kubernetes, ECS) restarts the container.
/health/ready  "Can it serve traffic?" Checks PostgreSQL. If this fails, the
               load balancer stops sending traffic but does NOT restart it.
"""

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

READINESS_TIMEOUT_SECONDS = 2.0


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get("/live", summary="Liveness probe")
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    summary="Readiness probe (checks PostgreSQL)",
    responses={503: {"model": HealthResponse, "description": "Database unreachable"}},
)
async def ready(
    # `Annotated[type, Depends(fn)]`: "call get_db and inject what it yields".
    # NestJS comparison: constructor injection, but per endpoint parameter.
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
) -> HealthResponse:
    try:
        # asyncio.timeout bounds the wait, so a hung database can't hang the probe.
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            await db.execute(text("SELECT 1"))
    except Exception:
        # Full details go to OUR logs; the client only learns "unavailable"
        # (no hostnames, credentials or driver errors leak out).
        logger.warning("readiness check failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unavailable")
    return HealthResponse(status="ok")
