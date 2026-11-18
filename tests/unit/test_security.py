import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from tests.conftest import make_test_settings

SETTINGS = make_test_settings()

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


async def test_password_hash_is_argon2id_and_verifies() -> None:
    hashed = await hash_password("correct horse battery")

    assert hashed.startswith("$argon2id$")
    assert "correct horse battery" not in hashed
    assert await verify_password("correct horse battery", hashed) is True
    assert await verify_password("wrong password!!", hashed) is False


async def test_same_password_hashes_differently_each_time() -> None:
    # A random salt per hash: identical passwords don't produce identical hashes,
    # so precomputed "rainbow tables" are useless.
    assert await hash_password("same password 123") != await hash_password("same password 123")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def test_token_round_trip_returns_user_id() -> None:
    user_id = uuid.uuid4()

    token = create_access_token(user_id, SETTINGS)

    assert decode_access_token(token, SETTINGS) == user_id


def test_token_contains_required_claims() -> None:
    token = create_access_token(uuid.uuid4(), SETTINGS)
    # Decoding WITHOUT verification is fine for inspecting claims in a test.
    claims = jwt.decode(token, options={"verify_signature": False})

    assert set(claims) == {"sub", "iat", "exp", "iss", "aud"}
    assert claims["exp"] - claims["iat"] == SETTINGS.access_token_expire_minutes * 60


def test_expired_token_rejected() -> None:
    issued_long_ago = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(uuid.uuid4(), SETTINGS, now=issued_long_ago)

    with pytest.raises(InvalidTokenError, match="expired"):
        decode_access_token(token, SETTINGS)


def test_tampered_token_rejected() -> None:
    token = create_access_token(uuid.uuid4(), SETTINGS)
    header, payload, signature = token.split(".")
    forged_payload = jwt.utils.base64url_encode(
        jwt.utils.base64url_decode(payload).replace(b'"iss"', b'"iSs"')
    ).decode()

    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{forged_payload}.{signature}", SETTINGS)


def test_token_signed_with_another_secret_rejected() -> None:
    other = make_test_settings(jwt_secret="a-completely-different-secret-0123456789")
    token = create_access_token(uuid.uuid4(), other)

    with pytest.raises(InvalidTokenError, match="Signature"):
        decode_access_token(token, SETTINGS)


@pytest.mark.parametrize(
    ("override", "expected"),
    [({"jwt_audience": "another-service"}, "(?i)audience"), ({"jwt_issuer": "evil"}, "(?i)issuer")],
)
def test_token_for_other_audience_or_issuer_rejected(
    override: dict[str, str], expected: str
) -> None:
    # Same secret, but minted for someone else.
    token = create_access_token(uuid.uuid4(), make_test_settings(**override))

    with pytest.raises(InvalidTokenError, match=expected):
        decode_access_token(token, SETTINGS)


def test_unsigned_alg_none_token_rejected() -> None:
    # The classic attack: a token that claims it needs no signature.
    claims = {
        "sub": str(uuid.uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": SETTINGS.jwt_issuer,
        "aud": SETTINGS.jwt_audience,
    }
    token = jwt.encode(claims, key=None, algorithm="none")

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SETTINGS)


def test_token_missing_expiry_rejected() -> None:
    secret = SETTINGS.jwt_secret.get_secret_value()
    claims = {"sub": str(uuid.uuid4()), "iat": datetime.now(UTC), "iss": "taskflow-api"}
    token = jwt.encode({**claims, "aud": "taskflow-api"}, secret, algorithm="HS256")

    with pytest.raises(InvalidTokenError, match="exp"):
        decode_access_token(token, SETTINGS)


def test_token_with_non_uuid_subject_rejected() -> None:
    secret = SETTINGS.jwt_secret.get_secret_value()
    now = datetime.now(UTC)
    claims = {
        "sub": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": SETTINGS.jwt_issuer,
        "aud": SETTINGS.jwt_audience,
    }

    with pytest.raises(InvalidTokenError):
        decode_access_token(jwt.encode(claims, secret, algorithm="HS256"), SETTINGS)
