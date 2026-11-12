"""Entry point of the API.

`fastapi dev app/main.py` looks in this file for a variable named `app`
and serves it. Everything else (routes, schemas) is plugged into it here.
"""

from fastapi import FastAPI

from app.routers import tasks

# The FastAPI object IS your application. The title/description show up
# in the auto-generated docs at /docs.
app = FastAPI(
    title="Task Management API",
    description="A learning project for FastAPI.",
    version="0.1.0",
)

# A router is a mini-app holding a group of related routes.
# include_router() mounts all of its routes onto the main app.
app.include_router(tasks.router)


# A "path operation": HTTP method (GET) + path ("/") + the function that handles it.
# Whatever you return is converted to JSON automatically.
@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Task Management API is running. Visit /docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
