from typing import Literal

from pydantic import BaseModel

from app.modules.users.schemas import (
    ExistingPassword,
    NewPassword,
    NormalizedEmail,
    PersonName,
    RequestModel,
)


class RegisterRequest(RequestModel):
    name: PersonName
    email: NormalizedEmail
    password: NewPassword


class LoginRequest(RequestModel):
    email: NormalizedEmail
    # No minimum length here: a too-short password is simply wrong (401),
    # not a validation error that hints at the password rules.
    password: ExistingPassword


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds until the token expires
