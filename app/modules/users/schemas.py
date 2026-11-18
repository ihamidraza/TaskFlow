"""Request and response schemas (DTOs) for users.

Reusable field types are declared once with `Annotated[type, constraints...]`,
then used like normal types. NestJS comparison: class-validator decorators,
but attached to a type you can reuse across many DTOs.
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# Emails are compared and stored lowercased ("normalization"), so
# John@Example.com and john@example.com are the same account.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]

PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# SecretStr: never shown in repr()/logs. Passwords are NOT stripped: spaces count.
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=128)]
# For checking an existing password we only cap the length: hashing a 1 MB
# "password" would be an easy way to burn CPU (Argon2 is slow on purpose).
ExistingPassword = Annotated[SecretStr, Field(min_length=1, max_length=128)]


class RequestModel(BaseModel):
    # extra="forbid": unknown fields are a 422 error instead of silently ignored,
    # so a client can't sneak in {"is_active": true} or {"password_hash": ...}.
    model_config = ConfigDict(extra="forbid")


class UserRead(BaseModel):
    """Public view of a user. Note what's missing: password_hash."""

    # from_attributes=True lets Pydantic read an ORM object's attributes:
    # UserRead.model_validate(user_orm_object).
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    is_active: bool
    created_at: datetime


class UserUpdate(RequestModel):
    """PATCH body: send only the fields to change. An empty body is a no-op."""

    name: PersonName | None = None
    email: NormalizedEmail | None = None

    # Field validators only run for fields the client actually sent, so this
    # rejects an explicit `"name": null` while still allowing the field to be omitted.
    @field_validator("name", "email")
    @classmethod
    def _not_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("may be omitted but not null")
        return value


class PasswordChange(RequestModel):
    current_password: ExistingPassword
    new_password: NewPassword
