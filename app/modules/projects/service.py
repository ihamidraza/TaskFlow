"""Project and membership business logic.

Authorization lives HERE (spec 4: "implemented at the service layer"):
every function receives the caller's membership and checks the rules in
permissions.py before changing anything.

Error order, consistently:
  404  not a member of the project (it might as well not exist)
  403  a member, but the role isn't allowed to attempt this
  400  allowed to attempt, but it breaks a rule that applies to everyone
  409  conflicts with existing data
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.pagination import PageParams
from app.modules.projects import permissions, repository
from app.modules.projects.model import Project, ProjectMember, ProjectRole
from app.modules.projects.schemas import MemberAdd, ProjectCreate, ProjectUpdate
from app.modules.users import service as users_service
from app.modules.users.model import User


def _project_not_found() -> NotFoundError:
    # Same error for "doesn't exist" and "exists but you're not in it", so
    # nobody can discover other projects by guessing ids.
    return NotFoundError("Project not found", code="PROJECT_NOT_FOUND")


def _member_not_found() -> NotFoundError:
    return NotFoundError("Member not found", code="MEMBER_NOT_FOUND")


def _require(allowed: bool) -> None:
    if not allowed:
        raise PermissionDeniedError()


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


async def get_membership_or_404(
    session: AsyncSession, project_id: uuid.UUID, user: User
) -> ProjectMember:
    """The caller's membership (with its project loaded), or 404."""
    membership = await repository.get_membership(session, project_id, user.id, with_project=True)
    if membership is None:
        raise _project_not_found()
    return membership


async def _lock_and_recheck(session: AsyncSession, actor: ProjectMember) -> ProjectMember:
    """Start of every membership change: lock the project row, then re-read the
    caller's own membership UNDER the lock.

    The membership passed in was loaded at the start of the request. If another
    request demoted or removed this user in the meantime, the old role would be
    stale; re-reading it after the lock means decisions use current data.
    """
    if await repository.lock_project(session, actor.project_id) is None:
        raise _project_not_found()
    current = await repository.get_membership(
        session, actor.project_id, actor.user_id, with_project=True, refresh=True
    )
    if current is None:
        raise _project_not_found()  # removed from the project meanwhile
    return current


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


async def create_project(session: AsyncSession, owner: User, data: ProjectCreate) -> Project:
    """Project + owner membership in ONE transaction: both rows or neither."""
    project = Project(name=data.name, description=data.description, owner_id=owner.id)
    session.add(project)
    # flush sends the INSERT now (inside the open transaction), which gives
    # project.id a value; nothing is permanent until commit.
    await session.flush()
    repository.add_membership(session, project, owner.id, ProjectRole.OWNER)
    await session.commit()
    # If anything above raised, commit never ran. The session is closed at the
    # end of the request (get_db), which rolls back the half-done transaction.
    return project


async def list_my_projects(
    session: AsyncSession, user: User, params: PageParams
) -> tuple[list[Project], int]:
    return await repository.list_projects_for_user(
        session, user.id, limit=params.limit, offset=params.offset
    )


async def update_project(
    session: AsyncSession, membership: ProjectMember, changes: ProjectUpdate
) -> Project:
    _require(permissions.can_update_project(membership.role))
    project = membership.project
    values = changes.model_dump(exclude_unset=True)
    if not values:
        return project  # empty PATCH: no-op
    for field, value in values.items():
        setattr(project, field, value)
    await session.commit()
    return project


async def delete_project(session: AsyncSession, membership: ProjectMember) -> None:
    _require(permissions.can_delete_project(membership.role))
    # The database's ON DELETE CASCADE removes memberships and tasks in the
    # same statement (passive_deletes=True on the relationships).
    await session.delete(membership.project)
    await session.commit()


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


async def list_members(
    session: AsyncSession, membership: ProjectMember, params: PageParams
) -> tuple[Sequence[ProjectMember], int]:
    _require(permissions.can_view_project(membership.role))
    return await repository.list_members(
        session, membership.project_id, limit=params.limit, offset=params.offset
    )


async def add_member(
    session: AsyncSession, membership: ProjectMember, data: MemberAdd
) -> ProjectMember:
    actor = await _lock_and_recheck(session, membership)
    _require(permissions.can_add_member(actor.role, data.role))
    if data.role is ProjectRole.OWNER:
        raise BadRequestError(
            "Use the transfer-ownership endpoint to change the owner",
            code="USE_TRANSFER_OWNERSHIP",
        )

    user = await users_service.get_user_by_id(session, data.user_id)
    if user is None or not user.is_active:
        raise NotFoundError("User not found", code="USER_NOT_FOUND")
    if await repository.get_membership(session, actor.project_id, user.id) is not None:
        raise ConflictError("User is already a member of this project", code="ALREADY_A_MEMBER")

    member = repository.add_membership(session, actor.project, user.id, data.role)
    member.user = user  # set the relationship so the response can include it
    try:
        await session.commit()
    except IntegrityError:
        # The unique (project_id, user_id) constraint: a concurrent request won.
        await session.rollback()
        raise ConflictError(
            "User is already a member of this project", code="ALREADY_A_MEMBER"
        ) from None
    return member


async def change_member_role(
    session: AsyncSession, membership: ProjectMember, user_id: uuid.UUID, new_role: ProjectRole
) -> ProjectMember:
    actor = await _lock_and_recheck(session, membership)
    _require(permissions.can_change_member_role(actor.role))

    target = await repository.get_membership(session, actor.project_id, user_id, with_user=True)
    if target is None:
        raise _member_not_found()
    if target.role is ProjectRole.OWNER:
        raise BadRequestError(
            "The owner's role can only change through an ownership transfer",
            code="OWNER_ROLE_LOCKED",
        )
    if new_role is ProjectRole.OWNER:
        raise BadRequestError(
            "Use the transfer-ownership endpoint to change the owner",
            code="USE_TRANSFER_OWNERSHIP",
        )

    target.role = new_role
    await session.commit()
    return target


async def remove_member(
    session: AsyncSession, membership: ProjectMember, user_id: uuid.UUID
) -> None:
    actor = await _lock_and_recheck(session, membership)
    target = await repository.get_membership(session, actor.project_id, user_id)
    if target is None:
        raise _member_not_found()
    _require(permissions.can_remove_member(actor.role, target.role))
    if target.role is ProjectRole.OWNER:
        raise BadRequestError(
            "The owner can't be removed; transfer ownership first", code="CANNOT_REMOVE_OWNER"
        )

    # Both changes in one transaction: unassign their tasks, then remove them.
    await repository.unassign_member_tasks(session, actor.project_id, user_id)
    await session.delete(target)
    await session.commit()


async def transfer_ownership(
    session: AsyncSession, membership: ProjectMember, new_owner_id: uuid.UUID
) -> Project:
    actor = await _lock_and_recheck(session, membership)
    _require(permissions.can_transfer_ownership(actor.role))
    if new_owner_id == actor.user_id:
        raise BadRequestError("You already own this project", code="ALREADY_OWNER")

    target = await repository.get_membership(
        session, actor.project_id, new_owner_id, with_user=True
    )
    if target is None or not target.user.is_active:
        raise BadRequestError(
            "The new owner must be an active member of the project",
            code="INVALID_TRANSFER_TARGET",
        )

    # ORDER MATTERS. The partial unique index allows only one 'owner' row per
    # project, and it's checked on every UPDATE. SQLAlchemy doesn't promise to
    # send UPDATEs in the order we set attributes, so we flush the demotion
    # first, explicitly, before promoting the new owner.
    actor.role = ProjectRole.ADMIN
    await session.flush()
    target.role = ProjectRole.OWNER
    actor.project.owner_id = target.user_id
    await session.commit()  # all three changes become visible together
    return actor.project
