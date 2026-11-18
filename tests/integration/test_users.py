from httpx import AsyncClient

from tests.api_helpers import DEFAULT_PASSWORD, register, register_and_login

NEW_PASSWORD = "a brand new passphrase"

# ---------------------------------------------------------------------------
# PATCH /users/me
# ---------------------------------------------------------------------------


async def test_update_name_and_email(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.patch(
        "/api/v1/users/me",
        json={"name": "  Countess Ada ", "email": "Countess@Example.com"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Countess Ada"
    assert response.json()["email"] == "countess@example.com"


async def test_update_only_sent_fields(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.patch("/api/v1/users/me", json={"name": "Ada L."}, headers=headers)

    assert response.json()["email"] == "ada@example.com"  # untouched


async def test_empty_update_is_a_no_op(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.patch("/api/v1/users/me", json={}, headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Ada Lovelace"


async def test_update_to_taken_email_rejected(client: AsyncClient) -> None:
    await register(client, email="grace@example.com")
    headers = await register_and_login(client, email="ada@example.com")

    response = await client.patch(
        "/api/v1/users/me", json={"email": "GRACE@example.com"}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_update_rejects_null_and_protected_fields(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    null_name = await client.patch("/api/v1/users/me", json={"name": None}, headers=headers)
    protected = await client.patch("/api/v1/users/me", json={"is_active": False}, headers=headers)

    assert null_name.status_code == 422
    assert protected.status_code == 422


async def test_update_requires_authentication(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/users/me", json={"name": "Nobody"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /users/me/change-password
# ---------------------------------------------------------------------------


async def test_change_password(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )
    old_login = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": DEFAULT_PASSWORD}
    )
    new_login = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": NEW_PASSWORD}
    )

    assert response.status_code == 204
    assert old_login.status_code == 401
    assert new_login.status_code == 200


async def test_change_password_requires_correct_current_password(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": "not my password", "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"


async def test_change_password_to_same_password_rejected(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": DEFAULT_PASSWORD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_UNCHANGED"


async def test_change_password_enforces_password_rules(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    response = await client.post(
        "/api/v1/users/me/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "short"},
        headers=headers,
    )

    assert response.status_code == 422
