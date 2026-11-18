"""Password hashing and JWT access tokens.

Pure functions with no FastAPI or database imports, so they're easy to unit test.
"""

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

# Argon2id with pwdlib's recommended parameters. Argon2 is deliberately SLOW
# and memory-hungry (~64 MB per hash), so stolen hashes are expensive to crack.
_password_hash = PasswordHash.recommended()


async def hash_password(password: str) -> str:
    """Hash a password without blocking the event loop.

    Argon2 is CPU-bound (tens of milliseconds). Running it directly inside an
    `async def` would freeze EVERY request on the server for that time, because
    one event loop serves them all. run_in_threadpool moves the work to a worker
    thread and `await`s the result. NestJS comparison: like `bcrypt.hash()`
    (async, runs on libuv's thread pool) instead of `bcrypt.hashSync()`.
    """
    return await run_in_threadpool(_password_hash.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await run_in_threadpool(_password_hash.verify, password, password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _password_hash.hash("dummy-password-for-constant-time-login")


async def verify_password_against_dummy(password: str) -> None:
    """Spend the same time as a real check when the email doesn't exist.

    Otherwise "unknown email" answers in ~1 ms and "wrong password" in ~50 ms,
    and an attacker can tell which emails are registered just by timing.
    """
    await verify_password(password, await run_in_threadpool(_dummy_hash))


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------


class InvalidTokenError(Exception):
    """Token is missing, malformed, expired, tampered with, or meant for someone else."""


def create_access_token(
    user_id: uuid.UUID,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Sign a JWT whose subject (`sub`) is the user's id.

    The `*` makes everything after it keyword-only: callers must write
    `expires_delta=...`, which keeps call sites readable.
    """
    issued_at = now or datetime.now(UTC)
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),  # JWT requires `sub` to be a string
        "iat": issued_at,  # issued at
        "exp": issued_at + lifetime,  # expires at
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Verify a token and return the user id inside it.

    Checks the signature, expiry, issuer and audience, and requires every claim
    we issue. `algorithms=[...]` is an explicit allow-list: never let the token's
    own header choose the algorithm (the classic `alg: none` attack).
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        # `from exc` keeps the original error attached for our logs/debugging.
        raise InvalidTokenError(str(exc)) from exc
