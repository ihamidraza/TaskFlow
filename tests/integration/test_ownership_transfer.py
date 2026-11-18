import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectMember, ProjectRole
from tests.integration.conftest import Team


async def _roles(client: AsyncClient, team: Team) -> dict[str, str]:
    response = await client.get(f"{team.url}/members", headers=team.admin.headers)
    return {m["user"]["email"].split("@")[0]: m["role"] for m in response.json()["items"]}


async def test_transfer_updates_owner_and_both_roles(
    client: AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    response = await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": team.member.id},
        headers=team.owner.headers,
    )

    assert response.status_code == 200
    assert response.json()["owner_id"] == team.member.id
    assert await _roles(client, team) == {"owner": "admin", "admin": "admin", "member": "owner"}
    owners = await db_session.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == team.project.id, ProjectMember.role == ProjectRole.OWNER)
    )
    assert owners == 1


async def test_new_owner_gains_and_old_owner_loses_owner_powers(
    client: AsyncClient, team: Team
) -> None:
    await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": team.member.id},
        headers=team.owner.headers,
    )

    old_owner_delete = await client.delete(team.url, headers=team.owner.headers)
    new_owner_delete = await client.delete(team.url, headers=team.member.headers)

    assert old_owner_delete.status_code == 403
    assert new_owner_delete.status_code == 204


@pytest.mark.parametrize("actor", ["admin", "member"])
async def test_only_owner_can_transfer(client: AsyncClient, team: Team, actor: str) -> None:
    response = await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": getattr(team, actor).id},
        headers=getattr(team, actor).headers,
    )

    assert response.status_code == 403


async def test_target_must_be_an_active_member(
    client: AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    outsider = await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": team.outsider.id},
        headers=team.owner.headers,
    )
    team.member.user.is_active = False
    await db_session.flush()
    inactive = await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": team.member.id},
        headers=team.owner.headers,
    )

    for response in (outsider, inactive):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TRANSFER_TARGET"
    assert (await _roles(client, team))["owner"] == "owner"  # nothing changed


async def test_cannot_transfer_to_yourself(client: AsyncClient, team: Team) -> None:
    response = await client.post(
        f"{team.url}/transfer-ownership",
        json={"new_owner_id": team.owner.id},
        headers=team.owner.headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ALREADY_OWNER"
