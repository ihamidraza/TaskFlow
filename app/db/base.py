"""Base class for all SQLAlchemy ORM models (models arrive in Phase 2).

NestJS/TypeORM comparison: like the base every `@Entity()` shares. Every model
inherits from `Base`, which registers its table on `Base.metadata`. Alembic
reads that metadata to generate migrations.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names. Without this, Postgres invents names, and
# Alembic can't reliably find a constraint later to alter or drop it.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
