"""The current-user dependency: FastAPI's answer to NestJS's AuthGuard + @CurrentUser().

Any endpoint that declares `current_user: CurrentUser` is protected: FastAPI
runs get_current_user first, and if it raises, the endpoint never runs.
"""

import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.config import SettingsDep
from app.core.exceptions import AuthenticationError
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import DbSession
from app.modules.users.model import User

logger = logging.getLogger(__name__)

# Reads `Authorization: Bearer <token>` from the request. It also tells
# /docs where to get a token (tokenUrl), which adds the "Authorize" button.
# auto_error=False: return None instead of raising FastAPI's own 401, so the
# missing-token error uses our error format too.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: DbSession,
    settings: SettingsDep,
) -> User:
    """Dependencies can depend on other dependencies: this one needs the token,
    a database session and the settings, and FastAPI resolves all three first."""
    if token is None:
        raise AuthenticationError("Not authenticated", code="NOT_AUTHENTICATED")

    try:
        user_id = decode_access_token(token, settings)
    except InvalidTokenError as exc:
        # Log WHY (expired, bad signature...) for debugging; never log the token.
        logger.info("access token rejected", extra={"reason": str(exc)})
        raise AuthenticationError(code="INVALID_TOKEN") from None

    # Always reload the user: a valid token for a deactivated or deleted
    # account must stop working immediately, not when the token expires.
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError(code="INVALID_TOKEN")
    return user


# Use as a parameter type: `current_user: CurrentUser`.
CurrentUser = Annotated[User, Depends(get_current_user)]
