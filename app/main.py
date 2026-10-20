from datetime import date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware
from app.config import SECRET_KEY, SESSION_HTTPS_ONLY
from app.database import Base, engine, get_db
from app.models import User, Task, TaskActivity
from app.security import hash_password, verify_password
from app.schemas import RegisterIn, LoginIn, TaskIn, TaskOut, STATUSES, PRIORITIES

BASE_DIR = Path(__file__).resolve().parent.parent
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Todo Management API", description="A personal todo manager with secure sessions and status-transition rules.", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="todo_session", same_site="lax", https_only=SESSION_HTTPS_ONLY, max_age=60*60*8)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

ALLOWED_TRANSITIONS = {"Pending": {"In Progress"}, "In Progress": {"Completed", "Pending"}, "Completed": set()}

def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return db.get(User, user_id)

def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user

def owned_task(db: Session, task_id: int, user_id: int) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task

def record_activity(db: Session, task: Task, user: User, action: str, details: str = ""):
    db.add(TaskActivity(task_id=task.id, user_id=user.id, action=action, details=details))

def set_flash(request: Request, message: str, category: str = "success"):
    request.session["flash"] = {"message": message, "category": category}

def render(request: Request, template: str, context: dict, status_code: int = 200):
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request=request, name=template, context={**context, "flash": flash}, status_code=status_code)

@app.get("/", include_in_schema=False)
def root(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse("/dashboard" if current_user(request, db) else "/login", status_code=303)

@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(request: Request):
    return render(request, "register.html", {"request": request, "user": None})

@app.post("/register", include_in_schema=False)
def register_form(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    username, email = username.strip(), email.strip().lower()
    try:
        data = RegisterIn(username=username, email=email, password=password)
    except Exception as exc:
        set_flash(request, str(exc).splitlines()[-1][:220], "danger")
        return RedirectResponse("/register", status_code=303)
    existing = db.scalar(select(User).where(or_(func.lower(User.username) == username.lower(), func.lower(User.email) == email)))
    if existing:
        set_flash(request, "That username or email is already registered.", "danger")
        return RedirectResponse("/register", status_code=303)
    user = User(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    request.session.clear(); request.session["user_id"] = user.id
    set_flash(request, "Welcome! Your account is ready.")
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return render(request, "login.html", {"request": request, "user": None})

@app.post("/login", include_in_schema=False)
def login_form(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        set_flash(request, "Invalid username or password.", "danger")
        return RedirectResponse("/login", status_code=303)
    request.session.clear(); request.session["user_id"] = user.id
    set_flash(request, f"Welcome back, {user.username}!")
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, status_filter: str = "", priority: str = "", q: str = "", db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    stmt = select(Task).where(Task.owner_id == user.id)
    if status_filter in STATUSES: stmt = stmt.where(Task.status == status_filter)
    if priority in PRIORITIES: stmt = stmt.where(Task.priority == priority)
    if q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(needle), Task.description.ilike(needle), Task.tags.ilike(needle)))
    tasks = list(db.scalars(stmt.order_by(Task.due_date.is_(None), Task.due_date, Task.created_at.desc())).all())
    all_tasks = list(db.scalars(select(Task).where(Task.owner_id == user.id)).all())
    total = len(all_tasks); completed = sum(t.status == "Completed" for t in all_tasks)
    pending = sum(t.status == "Pending" for t in all_tasks)
    overdue = sum(t.due_date is not None and t.due_date < date.today() and t.status != "Completed" for t in all_tasks)
    upcoming = [t for t in all_tasks if t.due_date and date.today() <= t.due_date and (t.due_date-date.today()).days <= 7 and t.status != "Completed"]
    return render(request, "dashboard.html", {"request": request, "user": user, "tasks": tasks, "total": total, "pending": pending, "completed": completed, "overdue": overdue, "percent": round(completed/total*100) if total else 0, "upcoming": sorted(upcoming, key=lambda t:t.due_date)[:4], "today": date.today(), "status_filter": status_filter, "priority_filter": priority, "q": q, "statuses": sorted(STATUSES), "priorities": ["Low","Medium","High","Urgent"]})

@app.post("/tasks", include_in_schema=False)
def create_task_form(request: Request, title: str = Form(...), description: str = Form(""), priority: str = Form("Medium"), tags: str = Form(""), due_date: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    try:
        data = TaskIn(title=title, description=description, priority=priority, tags=tags, due_date=due_date or None)
    except Exception as exc:
        set_flash(request, "Please check the task details. " + str(exc).splitlines()[-1][:160], "danger")
        return RedirectResponse("/dashboard", status_code=303)
    task = Task(**data.model_dump(), owner_id=user.id)
    db.add(task); db.flush(); record_activity(db, task, user, "Created", "Task created"); db.commit()
    set_flash(request, "Task created successfully.")
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/tasks/{task_id}/edit", include_in_schema=False)
def edit_task_form(task_id: int, request: Request, title: str = Form(...), description: str = Form(""), priority: str = Form("Medium"), tags: str = Form(""), due_date: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    task = owned_task(db, task_id, user.id)
    try:
        data = TaskIn(title=title, description=description, status=task.status, priority=priority, tags=tags, due_date=due_date or None)
    except Exception:
        set_flash(request, "Please provide a valid title, priority, and due date.", "danger")
        return RedirectResponse("/dashboard", status_code=303)
    task.title, task.description, task.priority, task.tags, task.due_date = data.title, data.description, data.priority, data.tags, data.due_date
    task.updated_at = __import__("datetime").datetime.utcnow()
    record_activity(db, task, user, "Edited", "Task details updated"); db.commit()
    set_flash(request, "Task updated.")
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/tasks/{task_id}/transition", include_in_schema=False)
def transition_form(task_id: int, request: Request, new_status: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    task = owned_task(db, task_id, user.id)
    if new_status not in ALLOWED_TRANSITIONS.get(task.status, set()):
        set_flash(request, f"Invalid status transition: {task.status} → {new_status}.", "danger")
        return RedirectResponse("/dashboard", status_code=303)
    old = task.status; task.status = new_status
    record_activity(db, task, user, "Status changed", f"{old} → {new_status}"); db.commit()
    set_flash(request, f"Task moved to {new_status}.")
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/tasks/{task_id}/delete", include_in_schema=False)
def delete_task_form(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    task = owned_task(db, task_id, user.id)
    db.delete(task); db.commit()
    set_flash(request, "Task deleted.")
    return RedirectResponse("/dashboard", status_code=303)

# JSON API: session-authenticated and documented at /docs.
@app.post("/api/register", status_code=201)
def api_register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(or_(func.lower(User.username)==data.username.lower(), func.lower(User.email)==str(data.email).lower()))):
        raise HTTPException(status_code=409, detail="Username or email already registered.")
    user = User(username=data.username, email=str(data.email).lower(), password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}

@app.post("/api/login")
def api_login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.username)==data.username.strip().lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    request.session.clear(); request.session["user_id"] = user.id
    return {"message": "Login successful.", "user": {"id": user.id, "username": user.username}}

@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"message": "Logged out."}

@app.get("/api/tasks", response_model=list[TaskOut])
def api_list_tasks(status_filter: str | None = None, priority: str | None = None, q: str | None = None, request: Request = None, db: Session = Depends(get_db)):
    user = require_user(request, db)
    stmt = select(Task).where(Task.owner_id == user.id)
    if status_filter:
        if status_filter not in STATUSES: raise HTTPException(status_code=422, detail="Invalid status filter.")
        stmt = stmt.where(Task.status == status_filter)
    if priority:
        if priority not in PRIORITIES: raise HTTPException(status_code=422, detail="Invalid priority filter.")
        stmt = stmt.where(Task.priority == priority)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like), Task.tags.ilike(like)))
    return list(db.scalars(stmt.order_by(Task.created_at.desc())).all())

@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def api_create_task(data: TaskIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    task = Task(**data.model_dump(), owner_id=user.id)
    db.add(task); db.flush(); record_activity(db, task, user, "Created", "Task created"); db.commit(); db.refresh(task)
    return task

@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
def api_update_task(task_id: int, data: TaskIn, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db); task = owned_task(db, task_id, user.id)
    if data.status != task.status and data.status not in ALLOWED_TRANSITIONS[task.status]:
        raise HTTPException(status_code=409, detail=f"Invalid status transition: {task.status} → {data.status}.")
    old_status = task.status
    for key, value in data.model_dump().items(): setattr(task, key, value)
    if data.status != old_status: record_activity(db, task, user, "Status changed", f"{old_status} → {data.status}")
    record_activity(db, task, user, "Edited", "Task details updated"); db.commit(); db.refresh(task)
    return task

@app.post("/api/tasks/{task_id}/transition", response_model=TaskOut)
def api_transition(task_id: int, new_status: str, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db); task = owned_task(db, task_id, user.id)
    if new_status not in ALLOWED_TRANSITIONS.get(task.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid status transition: {task.status} → {new_status}.")
    old = task.status; task.status = new_status
    record_activity(db, task, user, "Status changed", f"{old} → {new_status}"); db.commit(); db.refresh(task)
    return task

@app.delete("/api/tasks/{task_id}", status_code=204)
def api_delete_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db); task = owned_task(db, task_id, user.id)
    db.delete(task); db.commit()
    return None

@app.get("/api/tasks/{task_id}/activity")
def api_task_activity(task_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db); task = owned_task(db, task_id, user.id)
    items = db.scalars(select(TaskActivity).where(TaskActivity.task_id==task.id).order_by(TaskActivity.created_at.desc())).all()
    return [{"action": x.action, "details": x.details, "created_at": x.created_at.isoformat()} for x in items]
