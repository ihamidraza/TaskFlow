"""Helpers for tests that talk to the API over HTTP (via the in-process client)."""

import uuid
from typing import Any

from httpx import AsyncClient

from app.core.security import create_access_token
from tests.conftest import make_test_settings

DEFAULT_PASSWORD = "correct horse battery staple"


async def register(
    client: AsyncClient,
    email: str = "ada@example.com",
    password: str = DEFAULT_PASSWORD,
    name: str = "Ada Lovelace",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def login(
    client: AsyncClient, email: str = "ada@example.com", password: str = DEFAULT_PASSWORD
) -> dict[str, str]:
    """Log in and return headers ready to pass as `headers=` on later requests."""
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def register_and_login(client: AsyncClient, email: str = "ada@example.com") -> dict[str, str]:
    await register(client, email=email)
    return await login(client, email=email)


def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    """Headers with a freshly minted token for an existing user.

    Skips the HTTP login (and its deliberately slow Argon2 check). Login itself
    is covered by tests/integration/test_auth.py.
    """
    return {"Authorization": f"Bearer {create_access_token(user_id, make_test_settings())}"}
