"""Async database engine, session factory, and the `get_db` dependency.

Three objects, three lifetimes:
  engine          one per app; owns the connection POOL
  sessionmaker    one per app; a factory that makes sessions
  AsyncSession    one per REQUEST; a unit of work (tracks objects, runs a transaction)

The engine is created in the app's lifespan (see app/main.py) and stored on
`app.state`, so it is opened and closed explicitly and tests can point it at
a different database.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        database_url,
        echo=echo,  # True prints every SQL statement (handy when learning)
        pool_size=5,  # connections kept open
        max_overflow=10,  # extra connections allowed under burst load
        pool_pre_ping=True,  # test a connection before use; survives DB restarts
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit. In async code,
    # reloading an expired attribute would need an `await` we can't do implicitly.
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one AsyncSession per request.

    A dependency that `yield`s works like a context manager:
      - code before `yield` runs before the endpoint
      - the yielded value is injected into the endpoint
      - code after `yield` (here: closing the session) runs after the response
    NestJS comparison: a REQUEST-scoped provider with built-in cleanup.

    It doesn't commit. Services own transaction boundaries (see the spec, 6.4).
    """
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


# A reusable "type + how to get it" alias. Endpoints write `session: DbSession`
# instead of repeating `Annotated[AsyncSession, Depends(get_db)]` everywhere.
DbSession = Annotated[AsyncSession, Depends(get_db)]
