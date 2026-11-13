# Learning Log: Task Management API

A running journal of what was built and why. Newest lessons go at the bottom.

---

## Lesson 1: Setting up FastAPI

### Run it

```bash
uv run fastapi dev app/main.py
```

Then open:
- http://127.0.0.1:8000/docs : interactive docs (Swagger UI). You can call every endpoint from here.
- http://127.0.0.1:8000/redoc : the same docs, different style.

`fastapi dev` auto-reloads when you save a file. For production you'd use `fastapi run` instead.

### 1. The tools

| Tool | What it is |
|------|------------|
| **uv** | A fast Python project manager. It installs Python, creates the virtual environment and installs packages. It replaces `pip` + `venv` + `pyenv`. |
| **FastAPI** | The web framework. You write Python functions; it turns them into HTTP endpoints. |
| **Pydantic** | Data validation library FastAPI is built on. You describe data with classes; it checks incoming data matches. |
| **Uvicorn** | The actual web server (ASGI server) that runs your FastAPI app. `fastapi dev` starts it for you. |

`fastapi[standard]` installs FastAPI plus the "standard" extras: uvicorn, the `fastapi` CLI, and a few helpers.

### 2. Commands that were run

```bash
uv init --app --python 3.13 .     # create pyproject.toml, .python-version, .gitignore, git repo
uv add "fastapi[standard]"        # install FastAPI and record it in pyproject.toml + uv.lock
```

What each generated file does:

- **`pyproject.toml`**: the project's ID card. Name, Python version, and the dependency list. You edit this (or let `uv add` edit it).
- **`uv.lock`**: the *exact* version of every package (including sub-dependencies). Guarantees everyone gets identical installs. Commit it, never edit it by hand.
- **`.python-version`**: tells uv which Python to use (3.13 here, picked over 3.15 because it's well supported by all libraries).
- **`.venv/`**: the **virtual environment**: a private folder of packages just for this project, so projects don't conflict with each other. Not committed to git.

`uv run <command>` runs a command *inside* the virtual environment, so you never need to "activate" it. (You still can: `source .venv/bin/activate`.)

### 3. Project structure

```
task-management/
├── app/
│   ├── __init__.py        # empty; marks `app` as a Python package so `from app...` imports work
│   ├── main.py            # creates the FastAPI app and plugs in routers
│   ├── schemas.py         # Pydantic models: the shape of request/response data
│   └── routers/
│       ├── __init__.py
│       └── tasks.py       # all /tasks endpoints
├── pyproject.toml
└── uv.lock
```

Why split files? Each file has one job. As the project grows (users, projects, auth...) each gets its own router and schemas, and `main.py` stays tiny.

### 4. Key concepts in the code

**Path operation**: method + path + function:
```python
@app.get("/health")
def health():
    return {"status": "ok"}  # dicts/models are turned into JSON automatically
```

**Where does a parameter come from?** FastAPI decides from the function signature:

| Looks like | It's a... | Example |
|---|---|---|
| name appears in the path `{task_id}` | **path** parameter | `GET /tasks/5` |
| simple type (`int`, `bool`, `str`) not in path | **query** parameter | `GET /tasks?completed=true` |
| Pydantic model | **request body** (JSON) | `POST /tasks` with `{"title": "..."}` |

**Type hints = validation.** `task_id: int` means `/tasks/abc` is automatically rejected with **422**. `Field(min_length=1)` means an empty title is rejected. You write zero validation code.

**Separate schemas for input and output.** `TaskCreate` (no `id`, client sends it), `TaskUpdate` (all optional, for PATCH), `Task` (has `id`, server returns it). The client should never pick the id.

**Routers**: `APIRouter(prefix="/tasks")` groups related endpoints; `app.include_router(...)` mounts them.

**Errors**: `raise HTTPException(status_code=404, detail="Task not found")`.

### 5. HTTP status codes used

| Code | Meaning | When |
|---|---|---|
| 200 | OK | successful GET / PATCH |
| 201 | Created | successful POST |
| 204 | No Content | successful DELETE (empty body) |
| 404 | Not Found | task id doesn't exist |
| 422 | Unprocessable Content | request data failed validation (FastAPI does this for you) |

### 6. Try it yourself

```bash
curl -X POST localhost:8000/tasks -H 'Content-Type: application/json' -d '{"title":"Learn FastAPI"}'
curl localhost:8000/tasks
curl -X PATCH localhost:8000/tasks/1 -H 'Content-Type: application/json' -d '{"completed":true}'
curl -X DELETE localhost:8000/tasks/1
```

Or just use `/docs`, which is easier. Then restart the server and notice the tasks are gone: that's because storage is an in-memory dict.

### Exercises

1. Add a `priority` field (`"low" | "medium" | "high"`, default `"medium"`). Hint: `Literal` from `typing`.
2. Add a `GET /tasks?search=word` filter that matches titles.
3. Send `{"title": 123}` to `POST /tasks`. What happens and why?

### Next lessons (suggested order)

1. Real database (SQLite + SQLModel) so data survives restarts
2. Tests with `pytest` + FastAPI's `TestClient`
3. Dependency injection (`Depends`), the FastAPI superpower
4. Users and authentication (JWT)

---

## Lesson 2: Pushing to GitHub

`uv init` already ran `git init`, so the folder was a git repo with no commits yet.

```bash
git add -A                         # stage every file (respecting .gitignore)
git commit -m "Initial FastAPI setup"
git remote add origin git@github.com:ihamidraza/TaskFlow.git
git push -u origin main            # -u remembers origin/main, so later just `git push`
```

What's NOT pushed, thanks to `.gitignore`: `.venv/` (anyone can recreate it with `uv sync`) and `__pycache__/` (compiled Python bytecode).
What IS pushed and matters: `uv.lock`, so a teammate running `uv sync` gets the exact same package versions.

---

## Lesson 3: Phase 1, Foundation

> The in-memory tasks code from Lesson 1 was removed. Tasks return in Phase 5,
> backed by PostgreSQL. It's still in git history (`git show 7a3321a`).

### What exists now

| File | Job | NestJS equivalent |
|---|---|---|
| `app/core/config.py` | Typed settings from env / `.env` | `ConfigModule` + Joi schema |
| `app/core/logging.py` | JSON log formatter | a custom `LoggerService` |
| `app/db/base.py` | `Base` class every model inherits | TypeORM entity base |
| `app/db/session.py` | Engine, session factory, `get_db()` | `DataSource` + request-scoped provider |
| `app/middleware/request_logging.py` | One log line per request | `LoggingInterceptor` |
| `app/modules/health/router.py` | `/health/live`, `/health/ready` | `@nestjs/terminus` |
| `app/api/v1/router.py` | Collects all `/api/v1` routers | `RouterModule` |
| `app/main.py` | App factory + lifespan | `main.ts` + `AppModule` |
| `alembic/` | Database migrations | TypeORM migrations |
| `compose.yaml` | PostgreSQL 17 (+ `taskflow_test` db) | same |

### Concept 1: pydantic-settings and failing fast

```python
class Settings(BaseSettings):
    database_url: PostgresDsn   # no default = required
    jwt_secret: SecretStr       # masked in logs as **********
```
Env vars map to fields by name. Types are converted (`"15"` -> `15`) and validated.
A missing `DATABASE_URL` crashes at **startup** with a clear error instead of
failing on the first request at 3 a.m. `@lru_cache` on `get_settings()` makes it a
lazy singleton.

### Concept 2: Dependency injection with `Depends` and `yield`

```python
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session          # injected into the endpoint
    # session closed here, after the response

async def ready(db: Annotated[AsyncSession, Depends(get_db)]): ...
```
Big difference from NestJS: there's no DI container or `@Injectable()`. FastAPI reads
the endpoint's parameters, sees `Depends(get_db)`, calls it, and injects the result.
Dependencies are plain functions, can depend on other dependencies, and are swapped
in tests with `app.dependency_overrides[get_db] = fake_get_db`.

### Concept 3: Engine vs session

- **Engine**: one per app. Holds the connection **pool** (5 kept open, up to 10 extra).
- **AsyncSession**: one per request. A unit of work: tracks objects, owns a transaction.
  **Never share a session between concurrent requests.**

`pool_pre_ping=True` is why `/health/ready` recovered by itself after Postgres
restarted: dead connections are detected and replaced.

### Concept 4: Lifespan

```python
@asynccontextmanager
async def lifespan(app):
    engine = create_engine(...)   # startup
    yield                         # app serves requests
    await engine.dispose()        # shutdown
```
Startup and shutdown live in one function, so whatever you open you close right
next to it. Replaces the deprecated `@app.on_event("startup")`.

### Concept 5: async and `await`

`async def` endpoints run on one event loop (like Node). `await db.execute(...)`
yields control while Postgres works, so other requests proceed. **Rule:** never call
blocking I/O (`requests.get`, `time.sleep`, sync DB drivers) inside `async def`;
it freezes every request. That's why the driver is `asyncpg`. Ruff's `ASYNC`
rules catch some of these mistakes.

`asyncio.timeout(2)` in the readiness check bounds the wait, the same idea as
`Promise.race` with a timer.

### Concept 6: Liveness vs readiness

- `/live`: is the process alive? Fails -> orchestrator **restarts** the container.
- `/ready`: can it serve traffic? Fails -> load balancer **stops routing** to it.
If `/live` checked the DB, a database blip would restart every API container for no reason.

### Concept 7: Alembic

`env.py` reads `DATABASE_URL` from `Settings` (no credentials in `alembic.ini`)
and points at `Base.metadata`. In Phase 2, `alembic revision --autogenerate` will
diff the models against the database and write a migration you **review** before
applying with `alembic upgrade head`.

The naming convention in `base.py` gives constraints predictable names like
`uq_users_email`, so later migrations can find and alter them.

### Concept 8: Testing

- `create_app(settings)` (the app factory) builds an app pointed at `taskflow_test`.
- `httpx.AsyncClient(transport=ASGITransport(app))` calls the app in-process, like supertest.
- Gotcha: `ASGITransport` doesn't run the lifespan, so `conftest.py` runs it with
  `app.router.lifespan_context(app)`.
- Fixtures are injected by **parameter name**: `async def test_x(client): ...`

### Gotcha we hit: macOS privacy and Docker bind mounts

Postgres couldn't read a mounted `./docker/postgres` folder. macOS blocks OrbStack
from reading `~/Desktop`. Fix: put the init SQL inline in `compose.yaml` using
`configs: content:`, so nothing is mounted.

### Commands

```bash
docker compose up -d                 # start Postgres
uv run fastapi dev app/main.py       # run API with reload
uv run pytest                        # tests
uv run ruff format . && uv run ruff check .   # format + lint
uv run mypy app tests alembic/env.py          # type check
uv run alembic current               # check migration state
```

### Exercises

1. Add `"db": "ok"` to the `/health/ready` response. Where do you change the model, and does `/docs` update?
2. Set `APP_ENV=production` and `DEBUG=true` in `.env`, then start the server. What happens?
3. Temporarily put `time.sleep(3)` in `/health/live`, then call `/health/ready` at the same time from another terminal. What happens to it? Then try `await asyncio.sleep(3)`.
