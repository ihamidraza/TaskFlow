import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.users.service import get_user_by_email
from tests.api_helpers import DEFAULT_PASSWORD, login, register, register_and_login
from tests.conftest import make_test_settings

SETTINGS = make_test_settings()

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def test_register_returns_public_profile(client: AsyncClient) -> None:
    body = await register(client, email="  Ada@Example.COM ", name="  Ada  ")

    assert body["email"] == "ada@example.com"  # normalized
    assert body["name"] == "Ada"  # trimmed
    assert body["is_active"] is True
    assert set(body) == {"id", "name", "email", "is_active", "created_at"}  # no password_hash


async def test_register_stores_a_hash_not_the_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client)

    user = await get_user_by_email(db_session, "ada@example.com")
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert DEFAULT_PASSWORD not in user.password_hash


async def test_duplicate_registration_rejected_ignoring_case(client: AsyncClient) -> None:
    await register(client, email="ada@example.com")

    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Imposter", "email": "ADA@example.com", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_short_password_rejected_without_echoing_it(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ada", "email": "ada@example.com", "password": "hunter2"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["loc"] == ["body", "password"]
    assert "hunter2" not in response.text


async def test_register_cannot_set_protected_fields(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Ada",
            "email": "ada@example.com",
            "password": DEFAULT_PASSWORD,
            "is_active": False,
            "password_hash": "x",
        },
    )

    assert response.status_code == 422
    rejected = {tuple(d["loc"]) for d in response.json()["error"]["details"]}
    assert rejected == {("body", "is_active"), ("body", "password_hash")}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "ADA@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert body["access_token"].count(".") == 2  # header.payload.signature


async def test_login_failures_are_indistinguishable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client, email="ada@example.com")
    await register(client, email="inactive@example.com")
    inactive = await get_user_by_email(db_session, "inactive@example.com")
    assert inactive is not None
    inactive.is_active = False
    await db_session.flush()

    attempts = [
        {"email": "ada@example.com", "password": "wrong password!!"},  # wrong password
        {"email": "nobody@example.com", "password": DEFAULT_PASSWORD},  # unknown email
        {"email": "inactive@example.com", "password": DEFAULT_PASSWORD},  # inactive account
    ]
    responses = [await client.post("/api/v1/auth/login", json=a) for a in attempts]

    assert {r.status_code for r in responses} == {401}
    assert len({r.text for r in responses}) == 1  # identical bodies: nothing to learn
    assert responses[0].json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_oauth2_form_login_works(client: AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/v1/auth/token", data={"username": "ada@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


# ---------------------------------------------------------------------------
# Protected endpoint: /auth/me
# ---------------------------------------------------------------------------


async def test_me_returns_current_user(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


async def test_me_without_token_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_me_with_expired_token_rejected(client: AsyncClient) -> None:
    body = await register(client)
    expired = create_access_token(
        uuid.UUID(body["id"]), SETTINGS, now=datetime.now(UTC) - timedelta(hours=1)
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_me_with_tampered_token_rejected(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    tampered = headers["Authorization"][:-2] + (
        "aa" if not headers["Authorization"].endswith("aa") else "bb"
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": tampered})

    assert response.status_code == 401


async def test_token_of_deactivated_user_stops_working(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await register_and_login(client)
    user = await get_user_by_email(db_session, "ada@example.com")
    assert user is not None
    user.is_active = False
    await db_session.flush()

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401


async def test_valid_token_for_unknown_user_rejected(client: AsyncClient) -> None:
    token = create_access_token(uuid.uuid4(), SETTINGS)

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_login_helper_smoke(client: AsyncClient) -> None:
    await register(client)
    assert (await login(client))["Authorization"].startswith("Bearer ")
