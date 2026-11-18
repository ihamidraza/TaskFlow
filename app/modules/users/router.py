from fastapi import APIRouter, status

from app.core.exceptions import error_responses
from app.db.session import DbSession
from app.dependencies.auth import CurrentUser
from app.modules.users import service as users_service
from app.modules.users.schemas import PasswordChange, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.patch(
    "/me",
    summary="Update the current user's profile",
    description="Send only the fields to change. An empty body changes nothing.",
    responses=error_responses(401, 409, 422),
)
async def update_me(changes: UserUpdate, current_user: CurrentUser, session: DbSession) -> UserRead:
    user = await users_service.update_profile(session, current_user, changes)
    return UserRead.model_validate(user)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current user's password",
    responses=error_responses(400, 401, 422),
)
async def change_my_password(
    data: PasswordChange, current_user: CurrentUser, session: DbSession
) -> None:
    await users_service.change_password(
        session,
        current_user,
        current_password=data.current_password.get_secret_value(),
        new_password=data.new_password.get_secret_value(),
    )
