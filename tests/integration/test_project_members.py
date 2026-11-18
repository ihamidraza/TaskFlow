import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project, make_task, make_user
from tests.integration.conftest import Team

# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_members_list_nests_public_user_info(client: AsyncClient, team: Team) -> None:
    response = await client.get(f"{team.url}/members", headers=team.member.headers)

    body = response.json()
    assert response.status_code == 200
    assert body["pagination"]["total"] == 3
    roles = {m["user"]["email"]: m["role"] for m in body["items"]}
    assert roles == {
        "owner@example.com": "owner",
        "admin@example.com": "admin",
        "member@example.com": "member",
    }
    assert set(body["items"][0]["user"]) == {"id", "name", "email"}  # no hash, no is_active


async def test_outsider_cannot_list_members(client: AsyncClient, team: Team) -> None:
    response = await client.get(f"{team.url}/members", headers=team.outsider.headers)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actor", "role", "expected"),
    [
        ("owner", "member", 201),
        ("owner", "admin", 201),
        ("admin", "member", 201),
        ("admin", "admin", 403),  # admins can't grant admin
        ("member", "member", 403),  # members can't modify membership
    ],
)
async def test_add_member_permissions(
    client: AsyncClient, team: Team, actor: str, role: str, expected: int
) -> None:
    response = await client.post(
        f"{team.url}/members",
        json={"user_id": team.outsider.id, "role": role},
        headers=getattr(team, actor).headers,
    )

    assert response.status_code == expected
    if expected == 201:
        assert response.json()["user"]["id"] == team.outsider.id
        assert response.json()["role"] == role


async def test_role_defaults_to_member(client: AsyncClient, team: Team) -> None:
    response = await client.post(
        f"{team.url}/members", json={"user_id": team.outsider.id}, headers=team.owner.headers
    )

    assert response.json()["role"] == "member"


async def test_added_member_gains_access(client: AsyncClient, team: Team) -> None:
    await client.post(
        f"{team.url}/members", json={"user_id": team.outsider.id}, headers=team.owner.headers
    )

    response = await client.get(team.url, headers=team.outsider.headers)

    assert response.status_code == 200


async def test_cannot_add_with_owner_role(client: AsyncClient, team: Team) -> None:
    response = await client.post(
        f"{team.url}/members",
        json={"user_id": team.outsider.id, "role": "owner"},
        headers=team.owner.headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "USE_TRANSFER_OWNERSHIP"


async def test_duplicate_membership_rejected(client: AsyncClient, team: Team) -> None:
    response = await client.post(
        f"{team.url}/members", json={"user_id": team.member.id}, headers=team.owner.headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_A_MEMBER"


async def test_unknown_or_inactive_user_not_found(
    client: AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    inactive = await make_user(db_session, is_active=False)

    unknown = await client.post(
        f"{team.url}/members", json={"user_id": str(uuid.uuid4())}, headers=team.owner.headers
    )
    deactivated = await client.post(
        f"{team.url}/members", json={"user_id": str(inactive.id)}, headers=team.owner.headers
    )

    assert unknown.status_code == deactivated.status_code == 404
    assert unknown.json() == deactivated.json()
    assert unknown.json()["error"]["code"] == "USER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Change role
# ---------------------------------------------------------------------------


async def test_owner_promotes_member_to_admin(client: AsyncClient, team: Team) -> None:
    response = await client.patch(
        f"{team.url}/members/{team.member.id}", json={"role": "admin"}, headers=team.owner.headers
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_admin_cannot_change_roles(client: AsyncClient, team: Team) -> None:
    response = await client.patch(
        f"{team.url}/members/{team.member.id}", json={"role": "admin"}, headers=team.admin.headers
    )

    assert response.status_code == 403


async def test_owner_role_cannot_be_changed_or_granted_here(
    client: AsyncClient, team: Team
) -> None:
    demote_owner = await client.patch(
        f"{team.url}/members/{team.owner.id}", json={"role": "member"}, headers=team.owner.headers
    )
    grant_owner = await client.patch(
        f"{team.url}/members/{team.member.id}", json={"role": "owner"}, headers=team.owner.headers
    )

    assert demote_owner.json()["error"]["code"] == "OWNER_ROLE_LOCKED"
    assert grant_owner.json()["error"]["code"] == "USE_TRANSFER_OWNERSHIP"
    assert demote_owner.status_code == grant_owner.status_code == 400


async def test_change_role_of_non_member_is_404(client: AsyncClient, team: Team) -> None:
    response = await client.patch(
        f"{team.url}/members/{team.outsider.id}", json={"role": "admin"}, headers=team.owner.headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MEMBER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actor", "target", "expected"),
    [
        ("owner", "admin", 204),
        ("owner", "member", 204),
        ("admin", "member", 204),
        ("admin", "admin", 403),  # can't remove themselves either: admins remove members only
        ("admin", "owner", 403),
        ("member", "member", 403),
    ],
)
async def test_remove_member_permissions(
    client: AsyncClient, team: Team, actor: str, target: str, expected: int
) -> None:
    response = await client.delete(
        f"{team.url}/members/{getattr(team, target).id}", headers=getattr(team, actor).headers
    )

    assert response.status_code == expected


async def test_owner_cannot_be_removed(client: AsyncClient, team: Team) -> None:
    response = await client.delete(
        f"{team.url}/members/{team.owner.id}", headers=team.owner.headers
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_REMOVE_OWNER"


async def test_removed_member_loses_access_immediately(client: AsyncClient, team: Team) -> None:
    assert (await client.get(team.url, headers=team.member.headers)).status_code == 200

    await client.delete(f"{team.url}/members/{team.member.id}", headers=team.owner.headers)

    # Same token, still valid, but no longer a member.
    assert (await client.get(team.url, headers=team.member.headers)).status_code == 404


async def test_removing_member_unassigns_only_their_tasks_in_this_project(
    client: AsyncClient, db_session: AsyncSession, team: Team
) -> None:
    here = await make_task(
        db_session, team.project, team.member.user, assignee_id=team.member.user.id
    )
    other_project = await make_project(db_session, team.member.user)
    elsewhere = await make_task(
        db_session, other_project, team.member.user, assignee_id=team.member.user.id
    )

    await client.delete(f"{team.url}/members/{team.member.id}", headers=team.owner.headers)
    await db_session.refresh(here)
    await db_session.refresh(elsewhere)

    assert here.assignee_id is None
    assert here.created_by == team.member.user.id  # history kept
    assert elsewhere.assignee_id == team.member.user.id  # other projects untouched
