import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum

if TYPE_CHECKING:
    from app.modules.projects.model import Project
    from app.modules.users.model import User


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # Database backstops for rules Pydantic will also check in Phase 5.
        # Names become ck_tasks_<name> via the naming convention.
        CheckConstraint("char_length(title) >= 3", name="title_min_length"),
        # completed_at is set if and only if the task is done.
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)",
            name="completed_at_matches_status",
        ),
        # Composite indexes for "tasks in project X filtered/sorted by Y".
        # Each starts with project_id, so they also serve plain project_id
        # lookups: a separate index on project_id alone would be redundant.
        Index("ix_tasks_project_id_status", "project_id", "status"),
        Index("ix_tasks_project_id_priority", "project_id", "priority"),
        Index("ix_tasks_project_id_created_at", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        str_enum(TaskStatus, "task_status"),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        str_enum(TaskPriority, "task_priority"),
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        # SET NULL: if the user row disappeared, the task stays, unassigned.
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: keep task history; users are deactivated, not deleted.
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped["Project"] = relationship(back_populates="tasks", lazy="raise")
    assignee: Mapped["User | None"] = relationship(
        back_populates="assigned_tasks", foreign_keys=[assignee_id], lazy="raise"
    )
    creator: Mapped["User"] = relationship(
        back_populates="created_tasks", foreign_keys=[created_by], lazy="raise"
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"
