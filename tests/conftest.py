"""Shared pytest fixtures (pytest discovers this file automatically).

NestJS comparison: like `Test.createTestingModule(...)` in a `beforeEach`,
but fixtures are injected into tests by parameter NAME.

Database strategy:
  1. Once per test run: rebuild the test database from migrations
     (downgrade to nothing, upgrade to head). This also tests the migrations.
  2. Per test: open a transaction, hand the test a session inside it, and
     ROLL BACK at the end. Every test starts with empty tables, and nothing
     needs truncating.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import Settings
from app.db.session import create_engine, get_db
from app.main import create_app

# Tests use the dedicated taskflow_test database, never the dev database.
# CI can point elsewhere by setting TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://taskflow:taskflow_dev@localhost:5432/taskflow_test",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_test_settings(**overrides: object) -> Settings:
    """Settings for tests. `_env_file=None` ignores your local .env, so tests
    behave the same on every machine."""
    values: dict[str, object] = {
        "app_env": "testing",
        "database_url": TEST_DATABASE_URL,
        "jwt_secret": "test-secret-not-for-production-0123456789",
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def alembic_config() -> Config:
    """Alembic config pointed at the TEST database (env.py keeps a URL that's
    already set instead of reading DATABASE_URL)."""
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Iterator[None]:
    """scope="session": runs ONCE for the whole test run.
    autouse=True: applies to every test without being requested by name.

    It's a sync fixture on purpose: Alembic's async env.py calls asyncio.run(),
    which can't run inside an already-running event loop.
    """
    config = alembic_config()
    command.downgrade(config, "base")  # start from an empty database
    command.upgrade(config, "head")
    yield


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # One engine per test: pytest-asyncio gives each test its own event loop,
    # and pooled asyncpg connections can't move between loops.
    test_engine = create_engine(TEST_DATABASE_URL)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose changes are ALWAYS rolled back after the test.

    join_transaction_mode="create_savepoint": if code under test calls
    session.commit(), that commits a SAVEPOINT inside our outer transaction,
    not the real transaction, so the final rollback still undoes everything.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture
async def app(settings: Settings, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    application = create_app(settings)

    # Dependency override: every endpoint that asks for get_db gets the test's
    # rolled-back session instead. NestJS comparison:
    # `Test.createTestingModule(...).overrideProvider(X).useValue(...)`.
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db

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
