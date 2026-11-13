# TaskFlow API

A multi-user task and project management API built with FastAPI, PostgreSQL and async SQLAlchemy. It's a learning project: see [LEARNING.md](LEARNING.md) for lesson notes and [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the full spec.

**Status:** Phase 1 (Foundation) complete.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker with Compose (Docker Desktop or OrbStack)

## Setup

```bash
cp .env.example .env          # then set JWT_SECRET to a random value
uv sync                       # install dependencies into .venv
docker compose up -d          # start PostgreSQL (creates taskflow + taskflow_test)
uv run alembic upgrade head   # apply migrations (none yet; models arrive in Phase 2)
uv run fastapi dev app/main.py
```

- API docs: http://127.0.0.1:8000/docs (Swagger) and http://127.0.0.1:8000/redoc
- Liveness: `GET /health/live`
- Readiness (checks PostgreSQL): `GET /health/ready`

## Development

```bash
uv run pytest                                  # tests (uses the taskflow_test database)
uv run ruff format . && uv run ruff check .    # format + lint
uv run mypy app tests alembic/env.py           # type check
```

## Database environment

```bash
docker compose stop           # stop, keep data
docker compose start          # start again
docker compose down           # remove container, keep data volume
docker compose down -v        # reset: delete ALL data (test db is recreated on next up)
```

## Project layout

```
app/
├── main.py              # app factory + lifespan
├── api/v1/router.py     # /api/v1 aggregator
├── core/                # config, logging
├── db/                  # Base model class, engine/session
├── middleware/          # request logging
└── modules/             # feature modules (health now; auth, users, projects, tasks later)
alembic/                 # migrations
tests/                   # unit/ and integration/
```
