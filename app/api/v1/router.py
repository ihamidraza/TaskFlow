"""Collects every versioned business router under /api/v1.

Each module's router gets added here as it's built (auth and users in Phase 3,
projects in Phase 4, tasks in Phase 5). Moving to /api/v2 later means
adding a second aggregator, not editing every module.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(users_router)
