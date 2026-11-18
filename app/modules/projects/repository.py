"""Database queries for projects and memberships.

Repositories only READ and WRITE. They never commit (the service owns the
transaction) and never check permissions (the service does that too).
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.projects.model import Project, ProjectMember, ProjectRole
from app.modules.tasks.model import Task


async def lock_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """SELECT ... FOR UPDATE: lock this project's row until the transaction ends.

    Any other transaction that tries to lock the same row WAITS here. All
    membership changes call this first, so changes to one project's members
    happen one after another instead of interleaving.

    populate_existing=True: if this Project is already in the session (the
    identity map), overwrite it with the freshly locked row instead of
    returning the possibly stale cached copy.
    """
    statement = (
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def get_membership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    with_project: bool = False,
    with_user: bool = False,
    refresh: bool = False,
) -> ProjectMember | None:
    statement = select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
    )
    # Relationships are lazy="raise", so say up front what will be needed.
    if with_project:
        statement = statement.options(selectinload(ProjectMember.project))
    if with_user:
        statement = statement.options(selectinload(ProjectMember.user))
    if refresh:
        statement = statement.execution_options(populate_existing=True)
    return await session.scalar(statement)


async def list_projects_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Project], int]:
    # Only projects the user is a member of: authorization is part of the query,
    # so the total count can never include projects they can't see.
    accessible = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
    )
    total = await session.scalar(select(func.count()).select_from(accessible.subquery()))
    rows = await session.scalars(
        # Deterministic order: newest first, id breaks ties, so a row can't
        # appear on two pages (or none) when timestamps are equal.
        accessible.order_by(Project.created_at.desc(), Project.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


async def list_members(
    session: AsyncSession, project_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[ProjectMember], int]:
    total = await session.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project_id)
    )
    rows = await session.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        # selectinload: ONE extra query loads the users for the whole page
        # (WHERE id IN (...)), instead of one query per member (the N+1 problem).
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.joined_at, ProjectMember.id)
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total or 0


def add_membership(
    session: AsyncSession, project: Project, user_id: uuid.UUID, role: ProjectRole
) -> ProjectMember:
    member = ProjectMember(project_id=project.id, user_id=user_id, role=role)
    session.add(member)
    return member


async def unassign_member_tasks(
    session: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """One UPDATE for all of the user's tasks in this project (not a loop).
    created_by is untouched, so task history keeps who created what."""
    await session.execute(
        update(Task)
        .where(Task.project_id == project_id, Task.assignee_id == user_id)
        .values(assignee_id=None)
    )
