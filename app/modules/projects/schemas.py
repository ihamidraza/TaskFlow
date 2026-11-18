import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.modules.projects.model import ProjectRole
from app.modules.users.schemas import RequestModel, UserSummary

ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
# The column is TEXT (unlimited); the API still caps it so one request can't
# store megabytes.
Description = Annotated[str, StringConstraints(max_length=10_000)]


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(RequestModel):
    name: ProjectName
    description: Description | None = None


class ProjectUpdate(RequestModel):
    """PATCH: send only what changes. `"description": null` clears it;
    `"name": null` is rejected (a project always has a name)."""

    name: ProjectName | None = None
    description: Description | None = None

    @field_validator("name")
    @classmethod
    def _name_not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("may be omitted but not null")
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------


class MemberRead(BaseModel):
    """A NESTED schema: `user` is itself a model. With from_attributes=True,
    Pydantic reads member.user (an ORM User) into a UserSummary automatically,
    as long as the relationship was loaded (selectinload) beforehand."""

    model_config = ConfigDict(from_attributes=True)

    user: UserSummary
    role: ProjectRole
    joined_at: datetime


class MemberAdd(RequestModel):
    user_id: uuid.UUID
    role: ProjectRole = ProjectRole.MEMBER


class MemberRoleUpdate(RequestModel):
    role: ProjectRole


class OwnershipTransfer(RequestModel):
    new_owner_id: uuid.UUID
