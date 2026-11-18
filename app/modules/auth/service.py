"""Registration, login and token issuing."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    verify_password,
    verify_password_against_dummy,
)
from app.modules.auth.schemas import RegisterRequest, TokenResponse
from app.modules.users import service as users_service
from app.modules.users.model import User


def _invalid_credentials() -> AuthenticationError:
    # ONE message for every failure (unknown email, wrong password, inactive
    # account), so the response never reveals which emails are registered.
    return AuthenticationError("Incorrect email or password", code="INVALID_CREDENTIALS")


async def register(session: AsyncSession, data: RegisterRequest) -> User:
    return await users_service.create_user(
        session,
        name=data.name,
        email=data.email,
        password=data.password.get_secret_value(),
    )


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await users_service.get_user_by_email(session, email)
    if user is None:
        await verify_password_against_dummy(password)  # same timing as a real check
        raise _invalid_credentials()
    if not await verify_password(password, user.password_hash):
        raise _invalid_credentials()
    if not user.is_active:
        raise _invalid_credentials()
    return user


def issue_access_token(user: User, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )
