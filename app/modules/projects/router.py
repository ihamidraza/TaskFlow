"""Project and membership routes. Each one: dependencies in, one service call, schema out."""

import uuid

from fastapi import APIRouter, Depends, status

from app.core.exceptions import error_responses
from app.core.pagination import Page, PageParamsDep
from app.db.session import DbSession
from app.dependencies.auth import CurrentUser, get_current_user
from app.dependencies.permissions import ProjectMembership
from app.modules.projects import service as projects_service
from app.modules.projects.schemas import (
    MemberAdd,
    MemberRead,
    MemberRoleUpdate,
    OwnershipTransfer,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)

# dependencies=[...] on the ROUTER: every route below requires a valid token,
# even one that forgets to ask for CurrentUser. Routes that need the user
# object still declare it; FastAPI runs get_current_user only once per request.
router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
    responses=error_responses(401),
)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a project (you become its owner)",
    responses=error_responses(422),
)
async def create_project(
    data: ProjectCreate, current_user: CurrentUser, session: DbSession
) -> ProjectRead:
    project = await projects_service.create_project(session, current_user, data)
    return ProjectRead.model_validate(project)


@router.get("", summary="List projects you belong to")
async def list_projects(
    current_user: CurrentUser, session: DbSession, page: PageParamsDep
) -> Page[ProjectRead]:
    projects, total = await projects_service.list_my_projects(session, current_user, page)
    return Page[ProjectRead].build(
        [ProjectRead.model_validate(p) for p in projects], total=total, params=page
    )


@router.get("/{project_id}", summary="Get a project", responses=error_responses(404))
async def get_project(membership: ProjectMembership) -> ProjectRead:
    return ProjectRead.model_validate(membership.project)


@router.patch(
    "/{project_id}",
    summary="Update a project (owner, admin)",
    responses=error_responses(403, 404, 422),
)
async def update_project(
    changes: ProjectUpdate, membership: ProjectMembership, session: DbSession
) -> ProjectRead:
    project = await projects_service.update_project(session, membership, changes)
    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project and its memberships and tasks (owner)",
    responses=error_responses(403, 404),
)
async def delete_project(membership: ProjectMembership, session: DbSession) -> None:
    await projects_service.delete_project(session, membership)


@router.post(
    "/{project_id}/transfer-ownership",
    summary="Make another member the owner; you become an admin (owner)",
    responses=error_responses(400, 403, 404, 422),
)
async def transfer_ownership(
    data: OwnershipTransfer, membership: ProjectMembership, session: DbSession
) -> ProjectRead:
    project = await projects_service.transfer_ownership(session, membership, data.new_owner_id)
    return ProjectRead.model_validate(project)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{project_id}/members", summary="List project members", responses=error_responses(404))
async def list_members(
    membership: ProjectMembership, session: DbSession, page: PageParamsDep
) -> Page[MemberRead]:
    members, total = await projects_service.list_members(session, membership, page)
    return Page[MemberRead].build(
        [MemberRead.model_validate(m) for m in members], total=total, params=page
    )


@router.post(
    "/{project_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Add a member (owner: admin or member; admin: member only)",
    responses=error_responses(400, 403, 404, 409, 422),
)
async def add_member(
    data: MemberAdd, membership: ProjectMembership, session: DbSession
) -> MemberRead:
    member = await projects_service.add_member(session, membership, data)
    return MemberRead.model_validate(member)


@router.patch(
    "/{project_id}/members/{user_id}",
    summary="Change a member's role between admin and member (owner)",
    responses=error_responses(400, 403, 404, 422),
)
async def change_member_role(
    user_id: uuid.UUID, data: MemberRoleUpdate, membership: ProjectMembership, session: DbSession
) -> MemberRead:
    member = await projects_service.change_member_role(session, membership, user_id, data.role)
    return MemberRead.model_validate(member)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member and unassign their tasks (owner; admin for members)",
    responses=error_responses(400, 403, 404),
)
async def remove_member(
    user_id: uuid.UUID, membership: ProjectMembership, session: DbSession
) -> None:
    await projects_service.remove_member(session, membership, user_id)
