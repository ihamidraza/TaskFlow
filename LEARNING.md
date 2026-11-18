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
    database_url: PostgresDsn  # no default = required
    jwt_secret: SecretStr  # masked in logs as **********
```
Env vars map to fields by name. Types are converted (`"15"` -> `15`) and validated.
A missing `DATABASE_URL` crashes at **startup** with a clear error instead of
failing on the first request at 3 a.m. `@lru_cache` on `get_settings()` makes it a
lazy singleton.

### Concept 2: Dependency injection with `Depends` and `yield`

```python
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session  # injected into the endpoint
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
    engine = create_engine(...)  # startup
    yield  # app serves requests
    await engine.dispose()  # shutdown
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

---

## Lesson 4: Phase 2, Database Models

### What exists now

| File | Job | TypeORM equivalent |
|---|---|---|
| `app/db/mixins.py` | Shared `id` + `created_at`/`updated_at` | abstract `BaseEntity` |
| `app/db/types.py` | `str_enum()`: enum stored as VARCHAR + CHECK | `@Column({ type: 'enum' })` |
| `app/db/models.py` | Imports every model (the registry) | `entities: [...]` |
| `app/modules/users/model.py` | `User` | `@Entity() class User` |
| `app/modules/projects/model.py` | `Project`, `ProjectMember`, `ProjectRole` | |
| `app/modules/tasks/model.py` | `Task`, `TaskStatus`, `TaskPriority` | |
| `alembic/versions/…_initial_schema.py` | The migration, reviewed by hand | generated migration |
| `tests/factories.py` | Helpers that create valid rows | test fixtures/builders |

### Concept 1: `Mapped[...]` is the type AND the column

```python
name: Mapped[str] = mapped_column(String(100))           # NOT NULL
description: Mapped[str | None] = mapped_column(Text)     # NULL allowed
owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
```
SQLAlchemy 2.x reads the type hint: `str | None` means nullable, `str` means NOT NULL,
`uuid.UUID` means a Postgres `UUID` column. mypy understands it with no plugin.
TypeORM needs both `@Column({ nullable: true })` and `string | null`; here one line does both.

### Concept 2: Relationships in async code (`lazy="raise"`)

```python
project: Mapped["Project"] = relationship(back_populates="tasks", lazy="raise")
```
- `back_populates` links both sides (`task.project` and `project.tasks`).
- `"Project"` is a **string**: the class lives in another module, and importing it
  would be circular. `if TYPE_CHECKING:` imports exist only for mypy.
- **Lazy loading doesn't work in async.** Sync SQLAlchemy runs a hidden query when you
  touch `task.project`; async can't (there's no `await`), and crashes with a
  confusing `MissingGreenlet` error. `lazy="raise"` makes it a clear error instead, and you
  load what you need explicitly:
  ```python
  await session.scalar(select(Task).options(selectinload(Task.project)))
  ```
  TypeORM comparison: like always passing `relations: [...]`, enforced.

### Concept 3: Choosing what happens on delete

| FK | ON DELETE | Why |
|---|---|---|
| members/tasks → project | CASCADE | Deleting a project removes them in the same statement |
| task.assignee_id → user | SET NULL | Task survives, unassigned |
| owner_id, created_by, member.user_id → user | RESTRICT | Users are deactivated, never deleted |

On the ORM side, `passive_deletes=True` means "don't load the children to delete them one by
one; the database cascades". Without it, `session.delete(project)` would SELECT every task first.

### Concept 4: Constraints the database enforces for you

- **Expression index:** `CREATE UNIQUE INDEX … ON users (lower(email))`, so uniqueness ignores case.
- **Partial index:** `CREATE UNIQUE INDEX … ON project_members (project_id) WHERE role = 'owner'`.
  Only owner rows are indexed, so there can be at most one per project. Consequence for
  Phase 4: ownership transfer must demote the old owner **before** promoting the new one.
- **CHECK:** `(status = 'done') = (completed_at IS NOT NULL)`. Compares two booleans:
  both true or both false.
- **Why bother, if Pydantic validates?** The API is one entry point. Scripts, migrations,
  future services and bugs are others. The database is the last line of defense.

### Concept 5: Enums: values vs names, VARCHAR vs native

```python
class TaskStatus(StrEnum):
    IN_PROGRESS = "in_progress"     # StrEnum members ARE strings
```
- SQLAlchemy stores the **name** (`IN_PROGRESS`) by default; `values_callable` makes it
  store the **value** (`in_progress`), which matches the API contract.
- `native_enum=False` gives `VARCHAR(32)` + `CHECK (status IN (...))` instead of a Postgres
  `ENUM` type, which is hard to change later (no easy remove/rename of values).

### Concept 6: When does a default run?

```python
user = User(name="Ada", email="a@x.com", password_hash="…")
user.id         # None! Column defaults don't run in __init__
await session.flush()
user.id         # UUID: generated when the INSERT was sent, still before commit
```
**flush** = send pending SQL to the database inside the current transaction.
**commit** = make the transaction permanent. You can flush many times before one commit.

`eager_defaults=True` (in `TimestampMixin`) uses `INSERT/UPDATE … RETURNING` to read back
database-generated values like `updated_at`, so reading them later needs no hidden query.

### Concept 7: Reviewing an autogenerated migration

`alembic revision --autogenerate` diffs `Base.metadata` against the database. **Always read
the output.** It can't detect everything (renames look like drop + add, which **loses data**;
some CHECK constraint changes are invisible). Our review checked names, ON DELETE rules, the
expression and partial indexes, and the downgrade order. The notes are at the top of the file.

Then: `downgrade base` → `upgrade head` (round trip), and `alembic check` (no drift).
`tests/integration/test_migrations.py` runs `alembic check` in every test run.

### Concept 8: Rollback-per-test isolation

```python
async with engine.connect() as connection:
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    await transaction.rollback()
```
Every test writes real rows to real Postgres, then everything is undone. Even a
`session.commit()` inside the code under test only commits a **savepoint**. After a full run
the test database has 0 rows. The `app` fixture also overrides `get_db` to hand out this
session: that's FastAPI's `dependency_overrides`, used heavily from Phase 3 on.

### Gotchas we hit

1. **Name clash:** `import app.db.models` in `main.py` binds the name `app` (the package),
   which `app = create_app()` then overwrote. mypy caught it. Fix: `from app.db import models`.
2. **Ruff thought `alembic` was our package** because of the `alembic/` folder, so it sorted
   imports wrongly. Fix: `known-third-party = ["alembic"]`.
3. **Migration template:** updated `alembic/script.py.mako` to modern typing
   (`str | None` instead of `Union`), so future migrations pass Ruff as generated.

### Commands

```bash
uv run alembic upgrade head          # apply migrations
uv run alembic downgrade base        # undo all (DESTROYS data)
uv run alembic check                 # models vs migrations drift check
docker compose exec db psql -U taskflow -d taskflow -c '\d tasks'   # inspect a table
```

### Exercises

1. Run `\d project_members` in psql. Find the partial index and its `WHERE`.
2. In psql, try `INSERT INTO users (name, email, password_hash) VALUES ('A','A@X.COM','x')` twice
   with different capitalisation. Which constraint fires?
3. Add a nullable `color: Mapped[str | None]` column to `Project`, run
   `alembic revision --autogenerate -m "project color"`, read the file, `upgrade head`, then
   `downgrade -1` and delete the file. (Practice only; don't commit it.)

---

## Lesson 5: Phase 3, Authentication

### What exists now

| File | Job | NestJS equivalent |
|---|---|---|
| `app/core/security.py` | Argon2 hashing, JWT create/decode | `bcrypt` + `@nestjs/jwt` `JwtService` |
| `app/core/exceptions.py` | `AppError` classes + handlers → spec error format | custom exceptions + global `ExceptionFilter` |
| `app/dependencies/auth.py` | `get_current_user`, `CurrentUser` | `JwtAuthGuard` + `@CurrentUser()` decorator |
| `app/modules/auth/` | register, login, `/token`, `/me` | `AuthModule` |
| `app/modules/users/` | schemas, service, `PATCH /me`, change password | `UsersModule` |

### Concept 1: Dependencies replace guards

```python
CurrentUser = Annotated[User, Depends(get_current_user)]

@router.get("/me")
async def me(current_user: CurrentUser) -> UserRead: ...
```
Declaring the parameter **is** the protection. FastAPI runs `get_current_user` first; if it
raises, the endpoint never runs. `get_current_user` itself depends on three other
dependencies (the token, `DbSession`, `SettingsDep`): FastAPI resolves the whole tree, and
caches each dependency once per request, so the session is shared.

The `Annotated` aliases (`DbSession`, `SettingsDep`, `CurrentUser`) are reusable
"type + how to get it" bundles. They're the closest thing to NestJS's `@Inject()`.

### Concept 2: Services raise domain errors, not HTTP errors

```python
raise ConflictError("Email is already registered", code="EMAIL_ALREADY_REGISTERED")
```
One handler (`app_error_handler`) turns any `AppError` into the right status and body. The
service never imports FastAPI, so it's reusable from a CLI or a background job, and easy to
unit test. **Services are plain async functions** taking the session as their first
argument: Python doesn't need a class + DI container to inject one dependency.

### Concept 3: Hashing without blocking the event loop

```python
return await run_in_threadpool(_password_hash.hash, password)
```
Argon2 takes ~30 ms of pure CPU **on purpose**. Called directly in `async def`, it would
freeze every request for 30 ms. `run_in_threadpool` runs it on a worker thread. We measured
it: `/health/live` answered in 9 ms while 5 logins were hashing.
(NestJS comparison: `bcrypt.hash()` vs `bcrypt.hashSync()`.)

### Concept 4: JWT validation: what we check and why

| Check | Stops |
|---|---|
| `algorithms=["HS256"]` allow-list | `alg: none` tokens with no signature |
| Signature with our secret (≥ 32 chars, not the placeholder) | Forged or edited tokens |
| `exp` | Stolen tokens being used forever |
| `iss` + `aud` | Tokens minted for another service with a shared secret |
| `require=[...]` | Tokens missing a claim (e.g. no `exp` = never expires) |
| Reload user from DB, check `is_active` | Deactivated users with a still-valid token |

The JWT payload is **signed, not encrypted**: anyone can base64-decode it. Never put secrets
in it. Ours holds only the user id.

### Concept 5: Not leaking information

- **Same error for every login failure** (unknown email, wrong password, inactive account).
- **Same timing too:** for an unknown email we still verify against a dummy hash. Measured:
  ~31 ms for both cases. Without it, "unknown email" would answer in ~1 ms.
- **422 responses don't echo input.** FastAPI's default body includes an `input` field, which
  would copy a rejected password into the response. Our handler keeps only `loc`, `message`, `type`.
- **`SecretStr` for passwords** in request models: `repr()` and logs show `**********`.
- **`extra="forbid"`** on request models: `{"is_active": true}` is a 422, not silently ignored.

### Concept 6: Pydantic types worth reusing

```python
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=128)]
```
Before-validators run before type checking, after-validators after. `max_length=128` on
passwords isn't a UX rule: it stops someone sending a 1 MB "password" to burn Argon2 CPU.

**PATCH null vs omitted:** `{"name": null}` is rejected, `{}` changes nothing. A
`field_validator` only runs for fields the client actually sent, which is what makes this work.

### Concept 7: Why `/auth/token` exists alongside `/auth/login`

The spec wants JSON login. Swagger's **Authorize** button speaks the OAuth2 password flow,
which posts **form data** (`username`, `password`) to `tokenUrl`. `/auth/token` accepts that
form and calls the same `authenticate()`, so /docs works end to end.

### Concept 8: Registration race conditions

```python
if await get_user_by_email(...): raise ConflictError(...)   # friendly, common case
session.add(user)
try: await session.commit()
except IntegrityError: ...                                    # two requests at once
```
Check-then-insert isn't atomic: two simultaneous requests can both pass the check. The
unique index on `lower(email)` (Phase 2) lets only one win, and we turn the loser's
`IntegrityError` into the same 409.

### Known limits (by spec)

- A password change doesn't invalidate existing tokens; they live until `exp` (max 30 min).
- No rate limiting yet on login/register: Phase 6, before any public deployment.
- `request_id` in error bodies: Phase 6.

### Commands

```bash
curl -X POST localhost:8000/api/v1/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Ada","email":"ada@example.com","password":"correct horse battery"}'
curl -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com","password":"correct horse battery"}'
curl localhost:8000/api/v1/auth/me -H "Authorization: Bearer <token>"
```

### Exercises

1. Paste a token into https://jwt.io (it's a test token, so that's fine). Find `sub`, `exp`, `aud`.
   What does that tell you about putting data in a JWT?
2. In `security.py`, temporarily replace `run_in_threadpool(_password_hash.hash, ...)` with a
   direct call. Run 5 concurrent logins and time `/health/live`. What changed?
3. Remove `extra="forbid"` from `RequestModel` and run the tests. Which test fails, and what
   would that bug allow in production?
