"""Collects every versioned business router under /api/v1.

Each module's router gets added here as it's built (auth and users in Phase 3,
projects in Phase 4, tasks in Phase 5). Moving to /api/v2 later means
adding a second aggregator, not editing every module.
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# e.g. later: api_router.include_router(auth_router)
