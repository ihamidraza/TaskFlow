"""Fixtures for integration tests (pytest merges this with tests/conftest.py)."""

from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectRole, User
from tests.api_helpers import auth_headers
from tests.factories import add_member, make_project, make_user


@dataclass
class Actor:
    user: User
    headers: dict[str, str]

    @property
    def id(self) -> str:
        return str(self.user.id)


@dataclass
class Team:
    """One project with a user in each role, plus an outsider."""

    project: Project
    owner: Actor
    admin: Actor
    member: Actor
    outsider: Actor

    @property
    def url(self) -> str:
        return f"/api/v1/projects/{self.project.id}"


async def _actor(db_session: AsyncSession, name: str) -> Actor:
    user = await make_user(db_session, email=f"{name}@example.com", name=name.title())
    return Actor(user=user, headers=auth_headers(user.id))


@pytest.fixture
async def team(db_session: AsyncSession) -> Team:
    owner = await _actor(db_session, "owner")
    admin = await _actor(db_session, "admin")
    member = await _actor(db_session, "member")
    outsider = await _actor(db_session, "outsider")

    project = await make_project(db_session, owner.user, name="Team Project")
    await add_member(db_session, project, owner.user, ProjectRole.OWNER)
    await add_member(db_session, project, admin.user, ProjectRole.ADMIN)
    await add_member(db_session, project, member.user, ProjectRole.MEMBER)
    return Team(project=project, owner=owner, admin=admin, member=member, outsider=outsider)
