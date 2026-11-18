"""Project-scoped access dependencies.

`membership: ProjectMembership` on a route with a `{project_id}` path parameter
means: "the logged-in user must be a member of this project; give me their
membership (role + project)". Non-members get 404.

The role checks (403) happen in the service, which receives this membership.
"""

import uuid
from typing import Annotated

from fastapi import Depends

from app.db.session import DbSession
from app.dependencies.auth import CurrentUser
from app.modules.projects import service as projects_service
from app.modules.projects.model import ProjectMember


async def get_project_membership(
    # Matched by NAME to `{project_id}` in the route path. Typed as UUID, so
    # /projects/not-a-uuid is a 422 before any database query.
    project_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> ProjectMember:
    return await projects_service.get_membership_or_404(session, project_id, current_user)


ProjectMembership = Annotated[ProjectMember, Depends(get_project_membership)]
