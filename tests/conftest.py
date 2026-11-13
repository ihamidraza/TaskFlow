"""Shared pytest fixtures (pytest discovers this file automatically).

NestJS comparison: like `Test.createTestingModule(...)` in a `beforeEach`,
but fixtures are injected into tests by parameter NAME.
"""

import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

# Tests use the dedicated taskflow_test database, never the dev database.
# CI can point elsewhere by setting TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://taskflow:taskflow_dev@localhost:5432/taskflow_test",
)


def make_test_settings(**overrides: object) -> Settings:
    """Settings for tests. `_env_file=None` ignores your local .env, so tests
    behave the same on every machine."""
    values: dict[str, object] = {
        "app_env": "testing",
        "database_url": TEST_DATABASE_URL,
        "jwt_secret": "test-secret-not-for-production",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    # httpx's ASGITransport does NOT run the lifespan, so run it explicitly:
    # this creates the engine on startup and disposes it on teardown.
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # Requests go straight into the app in-process: no server, no network.
    # NestJS comparison: supertest's `request(app.getHttpServer())`.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
