import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum

if TYPE_CHECKING:
    from app.modules.tasks.model import Task
    from app.modules.users.model import User


class ProjectRole(StrEnum):
    """StrEnum members ARE strings: ProjectRole.OWNER == "owner" is True.
    Pydantic schemas will reuse this same enum in Phase 4."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: a user who owns projects can't be deleted.
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )

    owner: Mapped["User"] = relationship(back_populates="owned_projects", lazy="raise")

    # cascade="all, delete-orphan": ORM-level, deleting a Project also deletes
    #   its members/tasks, and removing one from the list deletes that row.
    # passive_deletes=True: don't LOAD the children to delete them one by one;
    #   trust the database's ON DELETE CASCADE to do it in a single statement.
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class ProjectMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        # A user can be in a project only once.
        UniqueConstraint("project_id", "user_id"),
        # "Which projects is this user in?" (the unique constraint above
        # already covers lookups that start with project_id).
        Index("ix_project_members_user_id_project_id", "user_id", "project_id"),
        # PARTIAL unique index: only rows WHERE role = 'owner' are indexed,
        # so at most one owner row can exist per project_id.
        Index(
            "uq_project_members_one_owner_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[ProjectRole] = mapped_column(
        str_enum(ProjectRole, "project_role"),
        default=ProjectRole.MEMBER,
        server_default=ProjectRole.MEMBER.value,
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="members", lazy="raise")
    user: Mapped["User"] = relationship(back_populates="memberships", lazy="raise")

    def __repr__(self) -> str:
        return f"<ProjectMember project={self.project_id} user={self.user_id} role={self.role}>"
