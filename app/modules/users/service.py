"""User business logic.

Plain async functions that take the session as their first argument. No class
or DI container needed: FastAPI injects the session into the ROUTE, and the
route passes it along. Services raise AppErrors, never HTTPException, and own
the transaction (they decide when to commit).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError
from app.core.security import hash_password, verify_password
from app.modules.users.model import User
from app.modules.users.schemas import UserUpdate


def _email_taken() -> ConflictError:
    return ConflictError("Email is already registered", code="EMAIL_ALREADY_REGISTERED")


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    # session.get() looks up by primary key (and checks the session's cache first).
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    # Comparing lower(email) lets Postgres use the uq_users_email_lower index.
    statement = select(User).where(func.lower(User.email) == email.lower())
    return await session.scalar(statement)


async def create_user(session: AsyncSession, *, name: str, email: str, password: str) -> User:
    # Friendly check first: the common case gets a clean 409 without a failed INSERT.
    if await get_user_by_email(session, email) is not None:
        raise _email_taken()

    user = User(name=name, email=email, password_hash=await hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Two requests registering the same email at the same moment can both
        # pass the check above; the unique index lets only one INSERT win.
        # The only unique constraint on users is the email index.
        await session.rollback()
        raise _email_taken() from None
    return user


async def update_profile(session: AsyncSession, user: User, changes: UserUpdate) -> User:
    # exclude_unset=True: only the fields the client sent.
    values = changes.model_dump(exclude_unset=True)
    if not values:
        return user  # documented behavior: empty PATCH is a no-op

    new_email = values.get("email")
    if new_email is not None and new_email != user.email:
        existing = await get_user_by_email(session, new_email)
        if existing is not None and existing.id != user.id:
            raise _email_taken()

    for field, value in values.items():
        setattr(user, field, value)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise _email_taken() from None
    return user


async def change_password(
    session: AsyncSession, user: User, *, current_password: str, new_password: str
) -> None:
    if not await verify_password(current_password, user.password_hash):
        raise BadRequestError("Current password is incorrect", code="INVALID_CURRENT_PASSWORD")
    if new_password == current_password:
        raise BadRequestError(
            "New password must be different from the current password", code="PASSWORD_UNCHANGED"
        )

    user.password_hash = await hash_password(new_password)
    await session.commit()
    # Tokens issued before this change stay valid until they expire (no
    # revocation list in the MVP, per the spec).
