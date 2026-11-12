"""CRUD routes for tasks.

CRUD = Create, Read, Update, Delete. In REST APIs these map to HTTP methods:
  POST   /tasks        -> create
  GET    /tasks        -> list all
  GET    /tasks/{id}   -> read one
  PATCH  /tasks/{id}   -> update some fields
  DELETE /tasks/{id}   -> delete

Storage is a plain dict for now, so data is lost when the server restarts.
Swapping this for a real database is a good next learning step.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas import Task, TaskCreate, TaskUpdate

# prefix: every route below starts with /tasks
# tags: groups these routes together in /docs
router = APIRouter(prefix="/tasks", tags=["tasks"])

# Fake "database": maps task id -> Task
_tasks: dict[int, Task] = {}
_next_id = 1


def _get_or_404(task_id: int) -> Task:
    task = _tasks.get(task_id)
    if task is None:
        # Raising HTTPException stops the request and sends this error to the client.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


# response_model tells FastAPI what shape the response has (used for docs + filtering).
# status_code=201 means "Created", the conventional response to a successful POST.
@router.post("", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> Task:
    # Because `payload` is a Pydantic model, FastAPI reads it from the JSON BODY
    # and has already validated it before this line runs.
    global _next_id
    task = Task(id=_next_id, **payload.model_dump())
    _tasks[task.id] = task
    _next_id += 1
    return task


@router.get("", response_model=list[Task])
def list_tasks(completed: bool | None = None) -> list[Task]:
    # `completed` is not in the path and not a model, so it's a QUERY parameter:
    # GET /tasks?completed=true
    tasks = list(_tasks.values())
    if completed is not None:
        tasks = [t for t in tasks if t.completed == completed]
    return tasks


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: int) -> Task:
    # `task_id` matches `{task_id}` in the path, so it's a PATH parameter.
    # The `int` type hint means /tasks/abc is rejected with a 422 automatically.
    return _get_or_404(task_id)


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = _get_or_404(task_id)
    # exclude_unset=True keeps only the fields the client actually sent,
    # so omitted fields are left unchanged.
    changes = payload.model_dump(exclude_unset=True)
    updated = task.model_copy(update=changes)
    _tasks[task_id] = updated
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int) -> None:
    _get_or_404(task_id)
    del _tasks[task_id]
    # 204 = "No Content": success, with an empty body.
