from typing import TYPE_CHECKING

from sqlalchemy import Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

# Imports only for the type checker. At runtime these modules import each other,
# so a real import would be circular. Relationships refer to the other
# classes by NAME ("Project") and SQLAlchemy resolves them later.
if TYPE_CHECKING:
    from app.modules.projects.model import Project, ProjectMember
    from app.modules.tasks.model import Task


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # `Mapped[str]` (not `str | None`) -> NOT NULL. Optional types become nullable.
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))  # 320 = longest valid email
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    # --- Relationships -------------------------------------------------------
    # lazy="raise": accessing a relationship that wasn't loaded explicitly
    # (with selectinload/joinedload) raises a clear error instead of running a
    # hidden query. Hidden queries don't work in async code anyway.
    #
    # passive_deletes="all": if a User were deleted, don't let the ORM touch
    # these child rows; the database's RESTRICT foreign keys reject the delete.
    # (Users are deactivated with is_active, never deleted.)
    owned_projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", lazy="raise", passive_deletes="all"
    )
    memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user", lazy="raise", passive_deletes="all"
    )
    # Task has TWO foreign keys to users, so we must say which one each side uses.
    assigned_tasks: Mapped[list["Task"]] = relationship(
        back_populates="assignee",
        foreign_keys="Task.assignee_id",
        lazy="raise",
        passive_deletes=True,  # DB does ON DELETE SET NULL
    )
    created_tasks: Mapped[list["Task"]] = relationship(
        back_populates="creator",
        foreign_keys="Task.created_by",
        lazy="raise",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# Case-insensitive uniqueness, enforced by the DATABASE: an index on the
# expression lower(email). 'John@x.com' collides with 'john@x.com'.
# Defined after the class so it can reference the User.email column.
Index("uq_users_email_lower", func.lower(User.email), unique=True)
