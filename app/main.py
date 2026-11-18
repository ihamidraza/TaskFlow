"""Application entry point.

`fastapi dev app/main.py` imports this file and serves the variable `app`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db import models  # noqa: F401  (registers every model; see app/db/models.py)
from app.db.session import create_engine, create_sessionmaker
from app.middleware.request_logging import log_requests
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown in one function.

    Code before `yield` runs once at startup; code after runs once at shutdown.
    NestJS comparison: `onModuleInit` + `onApplicationShutdown` in one place.

    Creating the engine doesn't connect yet; connections open lazily on first
    use. No `create_all()` here: Alembic migrations own the schema.
    """
    settings: Settings = app.state.settings
    engine = create_engine(str(settings.database_url))
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    try:
        yield
    finally:
        # Close every pooled connection cleanly.
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """App factory: builds a fresh, configured FastAPI app.

    Tests call `create_app(test_settings)` to get an app pointed at the test
    database, without touching environment variables.
    """
    # Fail fast: invalid or missing config raises a ValidationError right here,
    # before the server accepts any request.
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.middleware("http")(log_requests)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
