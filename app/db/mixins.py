"""Columns shared by several models.

A mixin is a plain class whose attributes are copied into every model that
inherits it. NestJS/TypeORM comparison: an abstract `BaseEntity` with
`@PrimaryGeneratedColumn('uuid')` and `@CreateDateColumn`/`@UpdateDateColumn`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    # `Mapped[uuid.UUID]` is both the Python type hint AND the column type:
    # SQLAlchemy maps uuid.UUID to Postgres's native UUID type.
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        # Python-side default: generated in Python at FLUSH time (when the INSERT
        # is sent), so no round trip to the database is needed to learn it.
        # Note: `User(...).id` is still None right after construction; it gets a
        # value on `await session.flush()`, inside the transaction, before commit.
        default=uuid.uuid4,
        # Database-side default too, for rows inserted with raw SQL.
        server_default=func.gen_random_uuid(),
        sort_order=-10,  # put `id` first in the table
    )


class TimestampMixin:
    # DateTime(timezone=True) -> Postgres `timestamptz`: stored in UTC, and
    # Python gets timezone-aware datetimes back (never naive ones).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        sort_order=10,  # put timestamps last
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        # The ORM adds `updated_at = now()` to every UPDATE it issues.
        # Limitation: raw SQL UPDATEs outside the ORM won't bump it.
        onupdate=func.now(),
        sort_order=10,
    )

    # eager_defaults: fetch database-generated values (created_at, updated_at)
    # in the same INSERT/UPDATE via `RETURNING`. Without it, reading
    # `task.updated_at` after an update would need a hidden extra query,
    # which async SQLAlchemy can't do implicitly (it raises instead).
    __mapper_args__: dict[str, Any] = {"eager_defaults": True}
