"""Model registry: import every model module in one place.

Why it's needed:
  - Relationships refer to classes by name ("Project"). SQLAlchemy can only
    resolve those names once every model class has been imported.
  - Alembic autogenerate only sees tables registered on Base.metadata, which
    happens when a model module is imported.

When you add a model module, import it here. NestJS/TypeORM comparison: the
`entities: [...]` list in the DataSource config.
"""

from app.db.base import Base
from app.modules.projects.model import Project, ProjectMember, ProjectRole
from app.modules.tasks.model import Task, TaskPriority, TaskStatus
from app.modules.users.model import User

__all__ = [
    "Base",
    "Project",
    "ProjectMember",
    "ProjectRole",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
]
