# TaskFlow API — Complete Project Context & Implementation Specification

## 1. Project Overview

**Project Name:** TaskFlow API  
**Project Type:** RESTful Backend Application  
**Primary Language:** Python 3.12+  
**Framework:** FastAPI  
**Database:** PostgreSQL  
**Architecture:** Modular Monolith with Layered Architecture  
**Primary Objective:** Build a production-oriented Task Management API while learning FastAPI, Python backend development, asynchronous programming, database operations, authentication, authorization, and software engineering best practices.

### 1.1 Project Description

TaskFlow is a multi-user task and project management backend that allows users to organize work into projects, collaborate with other users, assign tasks, track progress, and manage task lifecycles.

The application should expose a well-designed REST API that can be consumed by web applications, mobile applications, or third-party integrations.

The initial implementation focuses exclusively on backend development. A frontend is not required.

The project must be designed to demonstrate real-world backend engineering practices rather than simply implementing basic CRUD operations.

The resulting application should be modular, maintainable, testable, secure, and extensible.

### 1.2 Learning Objectives

This is primarily a learning project for an experienced software engineer transitioning from Node.js/NestJS to Python/FastAPI.

The implementation should demonstrate the following concepts:

1. Python type hints and asynchronous programming.
2. FastAPI application structure and routing.
3. Pydantic request validation and response serialization.
4. FastAPI dependency injection.
5. Asynchronous database operations with SQLAlchemy.
6. PostgreSQL relational modeling.
7. Database schema migrations with Alembic.
8. Authentication using JWT.
9. Role-based access control (RBAC).
10. Middleware, exception handling, and application lifespan.
11. Pagination, filtering, and sorting.
12. Database transactions and concurrency handling.
13. Unit and integration testing.
14. Docker-based development and deployment.
15. Environment-based configuration.
16. Logging, observability, and API documentation.

The coding agent should favor clear, idiomatic Python and native FastAPI patterns.

Avoid unnecessarily complicated abstractions or reproducing NestJS architecture mechanically in Python.

---

# 2. Functional Requirements

## 2.1 User Management

Users should be able to:

- Register a new account.
- Authenticate using email and password.
- Retrieve their profile.
- Update their profile.
- Change their password.
- View projects they belong to.
- Log out at the client level by discarding an access token.

### User Attributes

- `id`: UUID, primary key.
- `name`: String, required.
- `email`: String, required, unique, case-insensitive.
- `password_hash`: String, required.
- `is_active`: Boolean, default true.
- `created_at`: Timestamp with timezone.
- `updated_at`: Timestamp with timezone.

### Business Rules

- Email addresses must be unique after normalization.
- Passwords must never be stored in plaintext.
- Password hashing must use Argon2 through `pwdlib`.
- Inactive users cannot authenticate or access protected endpoints.
- Sensitive information must never appear in API responses.
- Password changes require verification of the current password.
- Access tokens must expire automatically.
- The initial implementation uses short-lived access tokens and does not require refresh tokens.
- Logout does not immediately revoke an already issued JWT; immediate revocation is outside MVP scope.

## 2.2 Authentication

Use JWT-based bearer authentication.

### Required Endpoints

**POST `/api/v1/auth/register`**

Register a user.

Request:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "StrongPassword123!"
}
```

Response: HTTP 201
```json
{
  "id": "b35d9f85-3c72-4f47-a48d-a91a8f7d4235",
  "name": "John Doe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2026-11-12T10:00:00Z"
}
```

**POST `/api/v1/auth/login`**

Authenticate a user.

Use JSON request bodies for the project login endpoint.

Request:
```json
{
  "email": "john@example.com",
  "password": "StrongPassword123!"
}
```

Response:
```json
{
  "access_token": "<signed-jwt-token>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**GET `/api/v1/auth/me`**

Retrieve the current authenticated user.

**PATCH `/api/v1/users/me`**

Update current user profile.

**POST `/api/v1/users/me/change-password`**

Change the current user's password.

### JWT Requirements

- Use PyJWT.
- Use HS256 with a strong secret from environment configuration for this single-service learning project.
- Never hardcode secrets.
- Set `sub` to the user UUID.
- Include `iat`, `exp`, and optionally `iss` and `aud`.
- Validate JWT signature, expiration, and expected claims.
- Use an explicit allowed algorithm list.
- Reject malformed, expired, and invalid tokens.
- Return HTTP 401 for invalid authentication.
- Use `OAuth2PasswordBearer` for extracting bearer tokens from protected routes.
- Load the user from PostgreSQL after validating the token.
- Reject inactive users.

### Password Rules

- Minimum length: 12 characters.
- Maximum length: 128 characters.
- Use Argon2 hashing.
- Never log passwords.
- Never return password hashes.
- Use consistent authentication errors without disclosing whether the email exists.
- Apply rate limiting to authentication endpoints before public deployment.

---

# 3. Project Management

Users can create projects and collaborate with other users.

## 3.1 Project Attributes

- `id`: UUID, primary key.
- `name`: String, required, maximum 150 characters.
- `description`: Text, nullable.
- `owner_id`: UUID, foreign key to users.
- `created_at`: Timestamp with timezone.
- `updated_at`: Timestamp with timezone.

## 3.2 Project Operations

**POST `/api/v1/projects`**

Create a project.

```json
{
  "name": "AI Engineering Platform",
  "description": "Development of internal AI services"
}
```

The authenticated user becomes the project owner.

Creating a project must also create an owner membership in the same database transaction.

**GET `/api/v1/projects`**

List projects accessible to the current user.

**GET `/api/v1/projects/{project_id}`**

Retrieve an accessible project.

**PATCH `/api/v1/projects/{project_id}`**

Update project details.

Only owners and admins can update project metadata.

**DELETE `/api/v1/projects/{project_id}`**

Delete a project.

Only the project owner can delete a project.

For MVP, deletion permanently removes the project, its memberships, and associated tasks within one transaction. Implement database relationship behavior deliberately rather than relying on accidental cascades.

Return HTTP 204 on successful deletion.

## 3.3 Project Membership

Each project can have multiple users.

Membership attributes:

- `id`: UUID.
- `project_id`: UUID.
- `user_id`: UUID.
- `role`: Enum (`owner`, `admin`, `member`).
- `joined_at`: Timestamp with timezone.

Enforce a unique database constraint on `(project_id, user_id)`.

### Membership Endpoints

- `GET /api/v1/projects/{project_id}/members`
- `POST /api/v1/projects/{project_id}/members`
- `PATCH /api/v1/projects/{project_id}/members/{user_id}`
- `DELETE /api/v1/projects/{project_id}/members/{user_id}`

### Membership Business Rules

- The creator is automatically the owner.
- Each project has exactly one owner.
- Only the owner can transfer ownership.
- Admins can add and remove regular members.
- Admins cannot grant the owner role.
- Admins cannot promote users to admin.
- Members cannot modify membership.
- A project owner cannot be removed without an ownership transfer.
- Owner membership cannot be downgraded through the general membership update endpoint.
- Duplicate memberships are rejected.
- A user cannot assign tasks to someone outside the project.
- All membership mutations must be performed transactionally.

For MVP, owner transfer requires a dedicated endpoint:

`POST /api/v1/projects/{project_id}/transfer-ownership`

Request:
```json
{
  "new_owner_id": "7f1acdfd-ef69-45ce-9925-927f432d98ef"
}
```

Only the current owner may perform this operation. The target must already be an active project member.

Update the project owner and both membership roles atomically.

---

# 4. Role-Based Authorization

Authorization must be implemented at the service layer and enforced on every resource operation.

## 4.1 Roles

**Owner**

- Full project access.
- Manage project details.
- Manage membership and roles.
- Transfer ownership.
- Delete the project.
- Manage all project tasks.

**Admin**

- Read and update the project.
- Create, update, assign, and delete tasks.
- Invite regular members.
- Remove regular members.
- Cannot remove the owner.
- Cannot transfer ownership.
- Cannot delete the project.

**Member**

- View project details.
- View project members.
- Create tasks.
- Update tasks.
- Assign tasks to project members.
- Delete tasks.
- Cannot modify project metadata or membership.

For the initial implementation, all project members can manage project tasks. Fine-grained task permissions can be introduced later.

## 4.2 Authorization Matrix

| Operation | Owner | Admin | Member |
|---|---|---|---|
| View project | Yes | Yes | Yes |
| Update project | Yes | Yes | No |
| Delete project | Yes | No | No |
| List tasks | Yes | Yes | Yes |
| Create tasks | Yes | Yes | Yes |
| Update tasks | Yes | Yes | Yes |
| Delete tasks | Yes | Yes | Yes |
| Add regular members | Yes | Yes | No |
| Remove regular members | Yes | Yes | No |
| Assign admin role | Yes | No | No |
| Transfer ownership | Yes | No | No |

Never trust resource IDs supplied by clients as evidence of authorization.

Every project and task operation must verify the current user's membership and permissions.

Return HTTP 404 for project and task resources that do not exist or are inaccessible, to avoid exposing cross-project resource existence. Return HTTP 403 when an authenticated member can access the resource but lacks permission for the attempted action.

---

# 5. Task Management

## 5.1 Task Attributes

- `id`: UUID, primary key.
- `project_id`: UUID, foreign key to projects.
- `title`: String, required, 3–255 characters.
- `description`: Text, nullable.
- `status`: Enum (`todo`, `in_progress`, `done`).
- `priority`: Enum (`low`, `medium`, `high`, `urgent`).
- `assignee_id`: UUID, nullable, foreign key to users.
- `created_by`: UUID, foreign key to users.
- `due_date`: Timestamp with timezone, nullable.
- `completed_at`: Timestamp with timezone, nullable.
- `created_at`: Timestamp with timezone.
- `updated_at`: Timestamp with timezone.

## 5.2 Task Operations

**POST `/api/v1/tasks`**

Create a task in an accessible project.

Example:
```json
{
  "project_id": "e6b8055b-a6c7-444c-aab4-07f7a203b6bd",
  "title": "Implement authentication",
  "description": "Build JWT authentication using FastAPI",
  "priority": "high",
  "assignee_id": null,
  "due_date": "2026-12-01T18:00:00Z"
}
```

**GET `/api/v1/tasks`**

List tasks only from projects accessible to the authenticated user.

Support optional query parameters:

- `project_id`
- `status`
- `priority`
- `assignee_id`
- `search`
- `sort_by`
- `sort_order`
- `limit`
- `offset`

**GET `/api/v1/tasks/{task_id}`**

Retrieve a task.

**PATCH `/api/v1/tasks/{task_id}`**

Partially update a task.

**DELETE `/api/v1/tasks/{task_id}`**

Delete a task.

Return HTTP 204 on success.

**GET `/api/v1/projects/{project_id}/tasks`**

List tasks belonging to one accessible project.

## 5.3 Task Business Rules

- A task must belong to an existing project.
- Users can only create tasks in projects they belong to.
- Task assignees must be active members of the same project.
- Unassigned tasks are allowed.
- Default status is `todo`.
- Default priority is `medium`.
- When status changes to `done`, set `completed_at` to the current UTC timestamp.
- When a completed task is reopened, clear `completed_at`.
- Updates must not allow changing `project_id`, `created_by`, or creation timestamps.
- Due dates must contain timezone information.
- Task listing must never expose data from inaccessible projects.
- Task search should support case-insensitive matching on title and description.
- Empty PATCH requests should be rejected or explicitly treated as no-ops; choose one behavior and document it.
- Clearing nullable fields must be supported by explicitly sending `null`.
- Validate status and priority using enums or Literal types.
- Use server-generated UUIDs and timestamps.
- When a project member is removed, unassign their project tasks in the same transaction, while retaining their historical `created_by` references.

---

# 6. Database Architecture

Use PostgreSQL with SQLAlchemy 2.x asynchronous ORM.

## 6.1 Tables

1. `users`
2. `projects`
3. `project_members`
4. `tasks`

## 6.2 Relationships

- User → Projects: one-to-many ownership.
- User ↔ Projects: many-to-many through project memberships.
- Project → Tasks: one-to-many.
- User → Assigned Tasks: one-to-many.
- User → Created Tasks: one-to-many.

## 6.3 Database Requirements

- UUID primary keys.
- Foreign key constraints.
- Unique constraints.
- Relevant indexes.
- UTC-aware timestamps.
- Explicit database transactions.
- Async SQLAlchemy sessions.
- Connection pooling.
- Migrations using Alembic.

Recommended indexes:

- `users.email` unique index.
- `projects.owner_id`.
- `project_members(project_id, user_id)` unique.
- `project_members(user_id, project_id)`.
- `tasks.project_id`.
- `tasks.assignee_id`.
- `tasks(project_id, status)`.
- `tasks(project_id, priority)`.
- `tasks(project_id, created_at)`.

Avoid unnecessary indexing until query patterns justify it.

## 6.4 Database Session Management

Use `create_async_engine` and `async_sessionmaker`.

Create a FastAPI dependency named `get_db()` that yields an `AsyncSession`.

Each request must receive its own database session.

Do not share one mutable AsyncSession across concurrent requests or independent asyncio tasks.

Business services should own transaction boundaries for operations that modify multiple related entities.

Do not commit independently from every repository method.

## 6.5 Migrations

Use Alembic.

Requirements:

- Initialize an async-compatible migration environment.
- Import all ORM models into Alembic metadata.
- Generate the initial database migration.
- Review all generated migrations.
- Test migration upgrades.
- Ensure migrations run against a configured database.
- Do not use `Base.metadata.create_all()` as a substitute for migrations in the application startup flow.

---

# 7. FastAPI Application Architecture

Use a feature-based modular monolith.

Recommended structure:

```text
taskflow-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       └── router.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── dependencies/
│   │   ├── auth.py
│   │   └── permissions.py
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── users/
│   │   │   ├── model.py
│   │   │   ├── schemas.py
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   ├── projects/
│   │   │   ├── model.py
│   │   │   ├── schemas.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   └── tasks/
│   │       ├── model.py
│   │       ├── schemas.py
│   │       ├── router.py
│   │       ├── service.py
│   │       └── repository.py
│   └── middleware/
│       └── request_logging.py
├── alembic/
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile
├── compose.yaml
├── pyproject.toml
└── README.md
```

## 7.1 Layer Responsibilities

### Router Layer

Responsible for:

- Route definitions.
- Request validation.
- Response models.
- FastAPI dependency injection.
- Delegating operations to services.
- HTTP status codes.

Routers must not contain complex business logic.

### Service Layer

Responsible for:

- Business rules.
- Authorization enforcement.
- Coordinating repositories.
- Transaction boundaries.
- Application-level error handling.

Services should be independently testable.

### Repository Layer

Responsible for:

- SQLAlchemy queries.
- Data persistence.
- Filtering.
- Pagination.
- Database-specific operations.

Keep repository abstractions lightweight. Do not create an unnecessary generic repository framework.

### Schema Layer

Responsible for:

- Request DTOs.
- Response DTOs.
- Validation.
- Serialization.
- Typed enums.

Use Pydantic v2 conventions.

### Model Layer

Responsible for:

- SQLAlchemy database models.
- Relationships.
- Constraints.
- Database defaults.

---

# 8. FastAPI Concepts That Must Be Demonstrated

The project is intended to teach FastAPI thoroughly.

Therefore, the implementation must meaningfully demonstrate:

### 8.1 Routing

- `APIRouter`
- Route prefixes.
- Route tags.
- Request and response status codes.
- Query parameters.
- Path parameters.
- Request bodies.
- Response models.

### 8.2 Dependency Injection

- `Depends()`.
- Database session dependency.
- Current authenticated user dependency.
- Project membership dependency.
- Permission-checking dependencies.
- Dependency overrides in tests.

Avoid manually constructing dependencies inside endpoints when FastAPI dependency injection is appropriate.

### 8.3 Validation

- Pydantic BaseModel.
- Field constraints.
- Enum validation.
- Nested schemas where appropriate.
- Optional fields.
- Partial updates using `exclude_unset=True`.
- Response serialization using `from_attributes=True`.

### 8.4 Async Programming

- `async def` endpoints.
- `await` database operations.
- SQLAlchemy AsyncSession.
- Async context managers.
- Correct handling of blocking operations.
- Proper connection and resource cleanup.

Never block the event loop with synchronous network or database I/O.

### 8.5 Lifespan

Use FastAPI's lifespan context manager where startup and shutdown resource management is needed.

Do not open database connections globally per request or perform schema creation during application startup.

### 8.6 Middleware

Implement:

- Request ID propagation.
- Structured request logging.
- Request duration measurements.

Avoid logging:

- Passwords.
- JWT access tokens.
- Authorization headers.
- Sensitive request bodies.

### 8.7 Exception Handling

Introduce application-specific exceptions where useful.

Translate domain errors into consistent HTTP responses.

---

# 9. Error Handling Standards

Use an application-wide error response format.

Example:

```json
{
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project not found",
    "details": null
  },
  "request_id": "f3e43cfa-44ae-4f79-a663-9ae52dfd0caa"
}
```

Recommended status codes:

| Status | Usage |
|---|---|
| 200 | Successful read or update |
| 201 | Resource created |
| 204 | Resource deleted |
| 400 | Invalid business operation |
| 401 | Authentication required or invalid |
| 403 | Insufficient permissions |
| 404 | Resource not found or inaccessible |
| 409 | Uniqueness or state conflict |
| 422 | Request validation failure |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |

Create handlers for application errors, request validation errors, and unexpected exceptions.

Do not expose internal tracebacks, database queries, credentials, or other sensitive implementation details to API clients.

Log unexpected errors with request IDs for debugging.

---

# 10. Pagination, Filtering, and Sorting

Implement pagination for list endpoints.

MVP uses offset pagination.

Default values:

- `limit = 20`
- `offset = 0`
- Maximum limit: `100`

Example:

`GET /api/v1/tasks?status=todo&priority=high&limit=20&offset=0`

Response:

```json
{
  "items": [],
  "pagination": {
    "total": 0,
    "limit": 20,
    "offset": 0,
    "has_next": false
  }
}
```

Requirements:

- All filters must be applied before pagination.
- Count queries must use the same authorization filters.
- Use an explicit and deterministic sort order.
- Only allow sorting by approved fields.
- Never interpolate untrusted client-provided column names into SQL.
- Ensure users cannot infer inaccessible records through total counts.

Supported sorting fields:

- `created_at`
- `updated_at`
- `due_date`
- `priority`

Supported directions:

- `asc`
- `desc`

For priority sorting, use explicit ordering rather than alphabetical ordering.

---

# 11. Configuration Management

Use `pydantic-settings`.

Required settings:

```dotenv
APP_NAME=TaskFlow API
APP_ENV=development
DEBUG=true

DATABASE_URL=postgresql+asyncpg://taskflow:taskflow_dev@localhost:5432/taskflow

JWT_SECRET=replace-with-secure-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

LOG_LEVEL=INFO
```

Requirements:

- All configuration values should be typed.
- Fail fast when required configuration is missing.
- Never commit real secrets.
- Provide `.env.example`.
- Support development, testing, and production environments.
- Debug mode must be disabled in production.
- Validate configuration on application startup.

---

# 12. Testing Strategy

Use:

- pytest.
- pytest-asyncio.
- HTTPX.
- A dedicated PostgreSQL test database.

Do not mock the entire database for integration tests.

Use isolated test data and clean up between tests.

## 12.1 Unit Tests

Test:

- Password hashing and verification.
- JWT creation and verification.
- Permission decisions.
- Task status transitions.
- Domain validation.
- Pagination logic where appropriate.

## 12.2 Integration Tests

Test:

### Authentication

- User registration succeeds.
- Duplicate registration fails.
- Login succeeds with valid credentials.
- Login fails with invalid credentials.
- Protected endpoint rejects missing token.
- Protected endpoint rejects expired token.
- Inactive user access is rejected.

### Projects

- User creates a project.
- Creator becomes project owner.
- User can list their projects.
- Unauthorized user cannot access another project.
- Admin can update project information.
- Member cannot update project information.
- Owner can delete a project.

### Membership

- Owner can add members.
- Admin can add regular members.
- Member cannot add members.
- Duplicate membership fails.
- Owner cannot be removed through the standard endpoint.
- Ownership transfer succeeds atomically.
- Removed users immediately lose project access.

### Tasks

- Member can create a task.
- Invalid status is rejected.
- Unauthorized users cannot read a task.
- Task can be updated.
- Completed task receives `completed_at`.
- Reopened task clears `completed_at`.
- Nonmember cannot be assigned a task.
- Task can be deleted.
- Filtering, sorting, and pagination work.

### Security

- JWT tampering is rejected.
- Cross-project resource access is blocked.
- Inactive users cannot access resources.
- Attempted unauthorized membership changes are rejected.
- Client input cannot override protected model fields.

## 12.3 Testing Requirements

- Test success and failure cases.
- Prefer dependency overrides for test configuration.
- Do not connect tests to the development database.
- Include authorization regression tests.
- Make tests deterministic.
- CI should fail on test failures.
- Target at least 80% coverage of business-critical service code, while prioritizing meaningful test cases over the coverage percentage itself.

---

# 13. Development Tooling

Use modern Python development practices.

### Package Management

Use `uv` for dependency and virtual environment management.

### Formatting and Linting

Use Ruff.

### Type Checking

Use mypy or Pyright.

### Testing

Use pytest.

### Pre-commit Checks

Configure automated checks for:

- Formatting.
- Linting.
- Type checking.
- Tests.

### API Documentation

Use FastAPI's automatic OpenAPI documentation:

- `/docs`
- `/redoc`
- `/openapi.json`

Every endpoint should define meaningful request and response schemas, status codes, and descriptions.

---

# 14. Docker and Deployment

Provide a Dockerfile for the API.

Provide Docker Compose configuration for:

- FastAPI.
- PostgreSQL.

Requirements:

- Use a supported Python base image.
- Install application dependencies reproducibly.
- Use a non-root runtime user.
- Define container health checks where appropriate.
- Persist PostgreSQL data through a volume.
- Use environment variables for configuration.
- Do not bundle development secrets into Docker images.
- Keep migrations as an explicit deployment step.
- Document how to start, stop, rebuild, and reset the development environment.

The development environment must be reproducible on macOS and Linux.

---

# 15. Logging and Observability

Implement structured logging.

Each request should have:

- Request ID.
- HTTP method.
- Path.
- Response status.
- Request duration.

Include contextual information such as authenticated user ID when available and appropriate.

Never log passwords, bearer tokens, or sensitive request payloads.

Expose:

**GET `/health/live`**

Returns a simple liveness response.

**GET `/health/ready`**

Checks whether the application can reach PostgreSQL.

The readiness endpoint should not disclose database credentials or internal infrastructure details.

---

# 16. Security Requirements

Apply the following security practices:

1. Validate all incoming data using Pydantic.
2. Use parameterized SQLAlchemy queries.
3. Hash passwords with Argon2.
4. Validate JWT signatures and expiry.
5. Enforce project-scoped authorization.
6. Protect all private resource endpoints.
7. Avoid exposing user enumeration through login errors.
8. Restrict CORS to configured origins.
9. Do not hardcode secrets.
10. Avoid leaking sensitive data in errors or logs.
11. Validate sorting and filtering parameters.
12. Use least-privilege database credentials.
13. Rate-limit authentication endpoints before internet exposure.
14. Do not use wildcard CORS with credentialed browser requests.
15. Pin dependencies through a lockfile.
16. Avoid unnecessary production debug interfaces.

Security checks should be integrated into service logic and covered by automated tests.

---

# 17. API Versioning

All business endpoints must use:

`/api/v1`

Example:

```text
/api/v1/auth/register
/api/v1/auth/login
/api/v1/auth/me

/api/v1/users/me
/api/v1/users/me/change-password

/api/v1/projects
/api/v1/projects/{project_id}
/api/v1/projects/{project_id}/members
/api/v1/projects/{project_id}/tasks

/api/v1/tasks
/api/v1/tasks/{task_id}
```

Health endpoints may remain unversioned.

Use meaningful HTTP methods and status codes.

Do not introduce GraphQL, gRPC, microservices, or event-driven infrastructure unless explicitly requested.

---

# 18. Implementation Plan

Implement the project incrementally.

## Phase 1 — Foundation

Tasks:

1. Initialize the Python project with `uv`.
2. Create the virtual environment and dependency configuration.
3. Set up FastAPI.
4. Create the modular directory structure.
5. Add application settings.
6. Add structured logging.
7. Add health endpoints.
8. Configure PostgreSQL through Docker Compose.
9. Configure SQLAlchemy async sessions.
10. Initialize Alembic.

**Deliverable:** A running FastAPI application with a working PostgreSQL connection.

## Phase 2 — Database Models

Tasks:

1. Implement the User model.
2. Implement the Project model.
3. Implement the ProjectMember model.
4. Implement the Task model.
5. Configure relationships and constraints.
6. Implement timestamps and UUID generation.
7. Generate the initial migration.
8. Apply and verify the migration.

**Deliverable:** A fully migrated relational database.

## Phase 3 — Authentication

Tasks:

1. Implement registration schemas.
2. Implement password hashing.
3. Implement registration service.
4. Implement login service.
5. Generate JWTs.
6. Implement bearer token validation.
7. Create current-user dependency.
8. Add profile endpoints.
9. Add authentication tests.

**Deliverable:** Secure registration, login, and authenticated user access.

## Phase 4 — Project Management

Tasks:

1. Implement project schemas.
2. Implement project repository.
3. Implement project services.
4. Implement project CRUD endpoints.
5. Create owner membership on project creation.
6. Implement membership management.
7. Implement authorization policies.
8. Implement ownership transfer.
9. Add project integration tests.

**Deliverable:** Authenticated project collaboration with role-based access.

## Phase 5 — Task Management

Tasks:

1. Implement task schemas.
2. Implement task repository.
3. Implement task services.
4. Implement task CRUD endpoints.
5. Implement assignment validation.
6. Implement status transitions.
7. Implement filtering and sorting.
8. Implement pagination.
9. Add task integration tests.

**Deliverable:** Complete project-scoped task management.

## Phase 6 — Production Readiness

Tasks:

1. Add consistent exception handling.
2. Improve structured logging.
3. Add request IDs.
4. Add database readiness checks.
5. Add authentication rate limiting.
6. Add configuration validation.
7. Add Dockerfile.
8. Finalize Docker Compose.
9. Add linting and type checking.
10. Configure automated CI tests.
11. Complete the README.
12. Review authorization and transaction edge cases.

**Deliverable:** A documented, testable, containerized backend application.

---

# 19. Definition of Done

The project is complete when:

- All required API endpoints are implemented.
- Authentication works correctly.
- Authorization prevents cross-project data access.
- Database migrations are reproducible.
- Project membership constraints are enforced.
- Task assignments respect project membership.
- Filtering, sorting, and pagination work.
- Unit and integration tests pass.
- Docker Compose starts the application and PostgreSQL.
- Environment configuration is documented.
- API documentation is available.
- Logging and error responses are consistent.
- Code passes configured linting and type checks.
- The README explains setup, architecture, endpoints, and testing.
- No hardcoded credentials or sensitive information exist in source control.
- Business logic is separated from route handlers.
- The application follows idiomatic FastAPI and Python conventions.

---

# 20. Explicitly Out of Scope

Do not implement the following in the initial version:

- Frontend web application.
- Mobile application.
- OAuth / Google Sign-In.
- Email notifications.
- Real-time collaborative editing.
- Redis.
- Celery.
- Kafka.
- SQS.
- Microservices.
- Event sourcing.
- AI integrations.
- WebSockets.
- Refresh tokens.
- Complex workflow automation.
- File attachments.
- Public third-party integrations.

These features can be added in future learning phases.

Keep the MVP focused on mastering FastAPI and building a solid backend foundation.

---

# 21. Instructions for the AI Coding Agent

You are acting as a senior Python backend engineer and technical mentor.

Your objective is to implement TaskFlow API according to this specification while helping the developer learn FastAPI and Python backend engineering.

## Engineering Guidelines

1. Use Python 3.12+ and modern Python typing conventions.
2. Follow PEP 8 and idiomatic Python practices.
3. Use current stable, mutually compatible versions of dependencies.
4. Use asynchronous SQLAlchemy 2.x APIs.
5. Use Pydantic v2.
6. Prefer native FastAPI capabilities over unnecessary third-party frameworks.
7. Use feature-based architecture.
8. Keep route handlers lightweight.
9. Place business logic in services.
10. Use dependency injection for shared dependencies.
11. Use repositories where they help organize database access.
12. Handle errors explicitly.
13. Write readable, maintainable code.
14. Avoid premature abstractions.
15. Add useful type hints and docstrings where needed.
16. Write tests alongside implementation.
17. Never use hardcoded secrets.
18. Ensure authorization checks cannot be bypassed.
19. Use atomic transactions for multi-table operations.
20. Keep the implementation consistent across modules.

## Learning-Oriented Instructions

This project is a learning exercise, not merely a code generation task.

When implementing a feature:

- Explain what is being built.
- Explain why the particular FastAPI pattern was selected.
- Highlight Python-specific concepts when relevant.
- Explain how dependency injection works.
- Explain asynchronous execution where it matters.
- Relate concepts to Node.js/NestJS when helpful.
- Describe alternatives when there are meaningful engineering tradeoffs.
- Avoid lengthy explanations of trivial syntax.
- Favor practical engineering insights.

## Implementation Workflow

Work incrementally according to the implementation phases.

For each phase:

1. State the objective.
2. Identify the files being created or modified.
3. Implement the functionality.
4. Add relevant tests.
5. Run available formatting, linting, typing, and tests.
6. Fix failures.
7. Explain the implemented architecture and important decisions.
8. Provide commands for manual verification.
9. Summarize what has been completed and what remains.

Do not claim tests have passed unless they have actually been executed successfully.

Do not silently modify requirements.

If an ambiguity affects security, data integrity, or the API contract, state the assumption and choose a safe, consistent implementation.

Do not add unrequested infrastructure or frameworks.

## Important Agent Behavior

**Do not implement all phases in a single pass.**

Start with Phase 1 and proceed incrementally.

At the end of each phase, provide:

- Implemented features.
- Files created or modified.
- Important technical decisions.
- Tests executed and their results.
- Commands to run the application.
- Concepts learned.
- Next recommended phase.

Wait for explicit approval before moving to the next phase.

## Initial Task

Begin with **Phase 1 — Foundation**.

Set up the project using Python, uv, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker Compose, and pydantic-settings.

Implement:

- Project initialization.
- Recommended folder structure.
- Application entry point.
- Environment configuration.
- PostgreSQL connection management.
- SQLAlchemy async session factory.
- Alembic initialization.
- Basic request logging.
- Health endpoints.
- Initial testing configuration.

Verify that:

1. The FastAPI server starts successfully.
2. `/docs` displays the generated OpenAPI documentation.
3. `/health/live` returns a healthy response.
4. `/health/ready` verifies PostgreSQL connectivity.
5. Database configuration loads from environment variables.
6. The test suite can be executed.
7. Docker Compose can start the required development services.

After completing Phase 1, explain the implementation and stop before Phase 2.

**End of Project Context & Implementation Specification.**