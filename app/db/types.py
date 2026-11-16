"""Reusable column types."""

from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store a Python StrEnum as VARCHAR + a CHECK constraint (not a native PG ENUM).

    - native_enum=False: plain VARCHAR. Adding or removing values later is a
      simple constraint change; native Postgres ENUM types are awkward to alter.
    - create_constraint=True: the database still rejects unknown values.
    - values_callable: store the enum's VALUE ("in_progress"), not its NAME
      ("IN_PROGRESS"). SQLAlchemy stores names by default, a common surprise.
    - name: used for the CHECK constraint name (ck_<table>_<name>).
    - length=32: room for longer values later without widening the column
      (by default it's sized to the longest current value).
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
        length=32,
    )
