"""Pydantic models (schemas) describe the SHAPE of data going in and out.

FastAPI uses them to:
  1. Validate incoming JSON (wrong types -> automatic 422 error)
  2. Convert outgoing data to JSON
  3. Generate the docs at /docs
"""

from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    """Fields shared by every task schema."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None  # optional: may be missing or null
    completed: bool = False  # optional with a default


class TaskCreate(TaskBase):
    """What the client sends to CREATE a task (no id; the server assigns it)."""


class TaskUpdate(BaseModel):
    """What the client sends to UPDATE a task. Every field is optional,
    so the client can send only the fields it wants to change."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    completed: bool | None = None


class Task(TaskBase):
    """What the server sends BACK: includes the id."""

    id: int
