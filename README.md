# TaskFlow API

A multi-user task and project management API built with FastAPI, PostgreSQL and async SQLAlchemy. It's a learning project: see [LEARNING.md](LEARNING.md) for lesson notes and [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the full spec.

**Status:** Phase 3 (Authentication) complete.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker with Compose (Docker Desktop or OrbStack)

## Setup

```bash
cp .env.example .env          # then set JWT_SECRET to a random value
uv sync                       # install dependencies into .venv
docker compose up -d          # start PostgreSQL (creates taskflow + taskflow_test)
uv run alembic upgrade head   # create the tables
uv run fastapi dev app/main.py
```

- API docs: http://127.0.0.1:8000/docs (Swagger) and http://127.0.0.1:8000/redoc
- Liveness: `GET /health/live`
- Readiness (checks PostgreSQL): `GET /health/ready`

## API (so far)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register` | none | Create an account (201) |
| POST | `/api/v1/auth/login` | none | JSON login, returns a bearer token |
| POST | `/api/v1/auth/token` | none | Same login as form data (used by the Authorize button in /docs) |
| GET | `/api/v1/auth/me` | bearer | Current user |
| PATCH | `/api/v1/users/me` | bearer | Update name and/or email |
| POST | `/api/v1/users/me/change-password` | bearer | Change password (204) |

**Trying it in /docs:** register with `POST /auth/register`, click **Authorize**, enter your
email as the username plus your password, then call any protected endpoint.

Errors use one format: `{"error": {"code": "...", "message": "...", "details": ...}}`.

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

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"   # then REVIEW the file
uv run alembic upgrade head      # apply
uv run alembic downgrade -1      # undo the last migration
uv run alembic check             # fails if models and migrations differ
```

## Project layout

```
app/
├── main.py              # app factory + lifespan
├── api/v1/router.py     # /api/v1 aggregator
├── core/                # config, logging
├── db/                  # Base, mixins, model registry, engine/session
├── middleware/          # request logging
└── modules/             # feature modules: health, users, projects, tasks (models so far)
alembic/                 # migrations
tests/                   # unit/ and integration/
```
