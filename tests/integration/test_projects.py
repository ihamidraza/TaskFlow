import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Project, ProjectMember, Task
from app.modules.projects import repository
from app.modules.projects import service as projects_service
from app.modules.projects.schemas import ProjectCreate
from tests.api_helpers import auth_headers
from tests.factories import make_task, make_user
from tests.integration.conftest import Team

# ---------------------------------------------------------------------------
# Create + list
# ---------------------------------------------------------------------------


async def test_create_project_makes_creator_the_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user.id)

    response = await client.post(
        "/api/v1/projects", json={"name": "  Launch  ", "description": "Q4"}, headers=headers
    )
    members = await client.get(f"/api/v1/projects/{response.json()['id']}/members", headers=headers)

    assert response.status_code == 201
    assert response.json()["name"] == "Launch"
    assert response.json()["owner_id"] == str(user.id)
    [owner] = members.json()["items"]
    assert owner["role"] == "owner"
    assert owner["user"]["id"] == str(user.id)


async def test_create_project_is_atomic(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If creating the owner membership fails, the project must not exist either."""
    user = await make_user(db_session)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated failure after the project INSERT")

    monkeypatch.setattr(repository, "add_membership", explode)
    with pytest.raises(RuntimeError):
        await projects_service.create_project(db_session, user, ProjectCreate(name="Doomed"))
    await db_session.rollback()  # what closing the request's session does

    count = await db_session.scalar(select(func.count()).select_from(Project))
    assert count == 0


async def test_list_shows_only_my_projects(client: AsyncClient, team: Team) -> None:
    await client.post(
        "/api/v1/projects", json={"name": "Outsider's own"}, headers=team.outsider.headers
    )

    mine = await client.get("/api/v1/projects", headers=team.member.headers)
    theirs = await client.get("/api/v1/projects", headers=team.outsider.headers)

    assert [p["name"] for p in mine.json()["items"]] == ["Team Project"]
    assert [p["name"] for p in theirs.json()["items"]] == ["Outsider's own"]


async def test_list_is_paginated(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    headers = auth_headers(user.id)
    for name in ("one", "two", "three"):
        await client.post("/api/v1/projects", json={"name": name}, headers=headers)

    first = await client.get("/api/v1/projects?limit=2", headers=headers)
    second = await client.get("/api/v1/projects?limit=2&offset=2", headers=headers)
    too_big = await client.get("/api/v1/projects?limit=101", headers=headers)

    assert first.json()["pagination"] == {"total": 3, "limit": 2, "offset": 0, "has_next": True}
    assert second.json()["pagination"]["has_next"] is False
    names = [p["name"] for p in first.json()["items"] + second.json()["items"]]
    assert sorted(names) == ["one", "three", "two"]  # every project exactly once
    assert too_big.status_code == 422


async def test_projects_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/projects")).status_code == 401


# ---------------------------------------------------------------------------
# Read: 404 hides projects you're not in
# ---------------------------------------------------------------------------


async def test_member_can_view_project(client: AsyncClient, team: Team) -> None:
    response = await client.get(team.url, headers=team.member.headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Team Project"


async def test_outsider_gets_same_404_as_missing_project(client: AsyncClient, team: Team) -> None:
    hidden = await client.get(team.url, headers=team.outsider.headers)
    missing = await client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=team.outsider.headers)

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()  # indistinguishable
    assert hidden.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_admin_can_update_project(client: AsyncClient, team: Team) -> None:
    response = await client.patch(team.url, json={"name": "Renamed"}, headers=team.admin.headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


async def test_member_cannot_update_project(client: AsyncClient, team: Team) -> None:
    response = await client.patch(team.url, json={"name": "Nope"}, headers=team.member.headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_outsider_update_gets_404_not_403(client: AsyncClient, team: Team) -> None:
    response = await client.patch(team.url, json={"name": "Nope"}, headers=team.outsider.headers)

    assert response.status_code == 404


async def test_update_null_description_clears_it_but_null_name_rejected(
    client: AsyncClient, team: Team
) -> None:
    await client.patch(team.url, json={"description": "temp"}, headers=team.owner.headers)

    cleared = await client.patch(team.url, json={"description": None}, headers=team.owner.headers)
    null_name = await client.patch(team.url, json={"name": None}, headers=team.owner.headers)

    assert cleared.json()["description"] is None
    assert null_name.status_code == 422


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["admin", "member"])
async def test_only_owner_can_delete(client: AsyncClient, team: Team, role: str) -> None:
    actor = getattr(team, role)

    response = await client.delete(team.url, headers=actor.headers)

    assert response.status_code == 403


async def test_owner_deletes_project_with_members_and_tasks(
    client: AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    await make_task(db_session, team.project, team.member.user)
    project_id = team.project.id

    response = await client.delete(team.url, headers=team.owner.headers)
    after = await client.get(team.url, headers=team.owner.headers)

    assert response.status_code == 204
    assert after.status_code == 404
    for model in (ProjectMember, Task):
        remaining = await db_session.scalar(
            select(func.count()).select_from(model).where(model.project_id == project_id)
        )
        assert remaining == 0
