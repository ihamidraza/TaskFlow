"""Small helpers that build valid model objects for tests.

Each returns an object already added to the session and flushed, so it has
been INSERTed (inside the test's transaction) and can be referenced by others.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectMember, ProjectRole, Task, User


async def make_user(session: AsyncSession, email: str | None = None, **kwargs: object) -> User:
    user = User(
        name=kwargs.pop("name", "Test User"),
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        **kwargs,
    )
    session.add(user)
    await session.flush()  # sends the INSERT, without committing
    return user


async def make_project(session: AsyncSession, owner: User, **kwargs: object) -> Project:
    project = Project(name=kwargs.pop("name", "Test Project"), owner_id=owner.id, **kwargs)
    session.add(project)
    await session.flush()
    return project


async def add_member(
    session: AsyncSession,
    project: Project,
    user: User,
    role: ProjectRole = ProjectRole.MEMBER,
) -> ProjectMember:
    member = ProjectMember(project_id=project.id, user_id=user.id, role=role)
    session.add(member)
    await session.flush()
    return member


async def make_task(
    session: AsyncSession, project: Project, creator: User, **kwargs: object
) -> Task:
    task = Task(
        project_id=project.id,
        created_by=creator.id,
        title=kwargs.pop("title", "A test task"),
        **kwargs,
    )
    session.add(task)
    await session.flush()
    return task
