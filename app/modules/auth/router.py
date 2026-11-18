"""Auth routes. Thin on purpose: validate input, call the service, shape the output."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import SettingsDep
from app.core.exceptions import error_responses
from app.db.session import DbSession
from app.dependencies.auth import CurrentUser
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses=error_responses(409, 422),
)
async def register(data: RegisterRequest, session: DbSession) -> UserRead:
    user = await auth_service.register(session, data)
    # model_validate reads the ORM object's attributes (from_attributes=True);
    # only fields declared on UserRead make it into the response.
    return UserRead.model_validate(user)


@router.post(
    "/login",
    summary="Log in with email and password (JSON)",
    responses=error_responses(401, 422),
)
async def login(data: LoginRequest, session: DbSession, settings: SettingsDep) -> TokenResponse:
    user = await auth_service.authenticate(session, data.email, data.password.get_secret_value())
    return auth_service.issue_access_token(user, settings)


@router.post(
    "/token",
    summary="OAuth2 password flow (form data), used by the Authorize button in /docs",
    responses=error_responses(401, 422),
)
async def token(
    # OAuth2PasswordRequestForm reads form fields `username` and `password`.
    # Depends() with no argument means "build this class from the request".
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DbSession,
    settings: SettingsDep,
) -> TokenResponse:
    # Same login, different input format. `username` holds the email.
    user = await auth_service.authenticate(session, form.username.strip(), form.password)
    return auth_service.issue_access_token(user, settings)


@router.get("/me", summary="Get the current user", responses=error_responses(401))
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
