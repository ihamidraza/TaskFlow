from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.conftest import make_test_settings


async def test_live_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_ok_when_database_reachable(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_returns_503_without_leaking_details_when_database_unreachable() -> None:
    # Port 1 has nothing listening, so the connection is refused immediately.
    settings = make_test_settings(
        database_url="postgresql+asyncpg://taskflow:taskflow_dev@127.0.0.1:1/taskflow_test"
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}  # no hostnames, no error text


async def test_openapi_docs_available(client: AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200
