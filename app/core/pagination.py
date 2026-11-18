"""Offset pagination shared by every list endpoint.

Request:  ?limit=20&offset=0
Response: {"items": [...], "pagination": {"total": 42, "limit": 20, "offset": 0, "has_next": true}}
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Self

from fastapi import Depends, Query
from pydantic import BaseModel

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def get_page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> PageParams:
    """A dependency that reads and validates the two query parameters once,
    so every list endpoint gets identical rules (max 100, no negative offset)."""
    return PageParams(limit=limit, offset=offset)


PageParamsDep = Annotated[PageParams, Depends(get_page_params)]


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int
    has_next: bool


class Page[T](BaseModel):
    """A GENERIC model: Page[ProjectRead], Page[MemberRead], later Page[TaskRead].

    `class Page[T]` is Python 3.12+ syntax for a type parameter (like
    `class Page<T>` in TypeScript). Pydantic builds a concrete model per T,
    and /docs shows each one, e.g. `Page[ProjectRead]`.
    """

    items: list[T]
    pagination: PageMeta

    @classmethod
    def build(cls, items: Sequence[T], *, total: int, params: PageParams) -> Self:
        return cls(
            items=list(items),
            pagination=PageMeta(
                total=total,
                limit=params.limit,
                offset=params.offset,
                has_next=params.offset + len(items) < total,
            ),
        )
