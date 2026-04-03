import os
import sqlite3
from contextlib import contextmanager
from typing import Literal

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", os.urandom(32).hex()),
)

templates = Jinja2Templates(directory="templates")


# Database setup


def init_db():
    conn = sqlite3.connect('todo.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            priority TEXT DEFAULT 'medium'
        )
    ''')
    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect('todo.db')
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    init_db()


VALID_PRIORITIES = {"low", "medium", "high"}


# Flash message helpers


def flash(request: Request, message: str, category: str = "success"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"category": category, "message": message})


def get_flashed_messages(request: Request):
    messages = request.session.pop("_messages", [])
    return messages


# Routes


@app.get('/')
def index(request: Request):
    with get_db() as conn:
        todos = conn.execute(
            'SELECT * FROM todos ORDER BY created_at DESC').fetchall()
    return templates.TemplateResponse('index.html', {
        'request': request,
        'todos': todos,
        'messages': get_flashed_messages(request),
    })


@app.post('/add')
def add_todo(request: Request, task: str = Form(None), priority: str = Form('medium')):
    if not task:
        flash(request, 'Task cannot be empty!', 'error')
        return RedirectResponse(url='/', status_code=303)

    if len(task) > 200:
        flash(request, 'Task is too long! Maximum 200 characters.', 'error')
        return RedirectResponse(url='/', status_code=303)

    if priority not in VALID_PRIORITIES:
        flash(request, 'Invalid priority!', 'error')
        return RedirectResponse(url='/', status_code=303)

    with get_db() as conn:
        conn.execute(
            'INSERT INTO todos (task, priority) VALUES (?, ?)', (task, priority))
        conn.commit()

    flash(request, 'Task added successfully!', 'success')
    return RedirectResponse(url='/', status_code=303)


@app.post('/toggle/{todo_id}')
def toggle_todo(request: Request, todo_id: int):
    with get_db() as conn:
        todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                            (todo_id,)).fetchone()

        if todo:
            new_status = not todo['completed']
            conn.execute('UPDATE todos SET completed = ? WHERE id = ?',
                         (new_status, todo_id))
            conn.commit()
            flash(request, f'Task {"completed" if new_status else "reopened"}!', 'success')
        else:
            flash(request, 'Task not found!', 'error')

    return RedirectResponse(url='/', status_code=303)


@app.post('/delete/{todo_id}')
def delete_todo(request: Request, todo_id: int):
    with get_db() as conn:
        todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                            (todo_id,)).fetchone()

        if todo:
            conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
            conn.commit()
            flash(request, 'Task deleted successfully!', 'success')
        else:
            flash(request, 'Task not found!', 'error')

    return RedirectResponse(url='/', status_code=303)


@app.get('/edit/{todo_id}')
def edit_todo_form(request: Request, todo_id: int):
    with get_db() as conn:
        todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                            (todo_id,)).fetchone()

    if not todo:
        flash(request, 'Task not found!', 'error')
        return RedirectResponse(url='/', status_code=303)

    return templates.TemplateResponse('edit.html', {
        'request': request,
        'todo': todo,
        'messages': get_flashed_messages(request),
    })


@app.post('/edit/{todo_id}')
def edit_todo(request: Request, todo_id: int, task: str = Form(None), priority: str = Form('medium')):
    with get_db() as conn:
        todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                            (todo_id,)).fetchone()

        if not todo:
            flash(request, 'Task not found!', 'error')
            return RedirectResponse(url='/', status_code=303)

        if not task:
            flash(request, 'Task cannot be empty!', 'error')
            return templates.TemplateResponse('edit.html', {
                'request': request,
                'todo': todo,
                'messages': get_flashed_messages(request),
            })

        if len(task) > 200:
            flash(request, 'Task is too long! Maximum 200 characters.', 'error')
            return templates.TemplateResponse('edit.html', {
                'request': request,
                'todo': todo,
                'messages': get_flashed_messages(request),
            })

        if priority not in VALID_PRIORITIES:
            flash(request, 'Invalid priority!', 'error')
            return templates.TemplateResponse('edit.html', {
                'request': request,
                'todo': todo,
                'messages': get_flashed_messages(request),
            })

        conn.execute('UPDATE todos SET task = ?, priority = ? WHERE id = ?',
                     (task, priority, todo_id))
        conn.commit()

    flash(request, 'Task updated successfully!', 'success')
    return RedirectResponse(url='/', status_code=303)


# API Routes


class TodoCreate(BaseModel):
    task: str = Field(..., min_length=1, max_length=200)
    priority: Literal['low', 'medium', 'high'] = 'medium'


@app.get('/api/todos')
def api_get_todos():
    with get_db() as conn:
        todos = conn.execute(
            'SELECT * FROM todos ORDER BY created_at DESC').fetchall()

    return [{
        'id': todo['id'],
        'task': todo['task'],
        'completed': bool(todo['completed']),
        'created_at': todo['created_at'],
        'priority': todo['priority']
    } for todo in todos]


@app.post('/api/todos', status_code=201)
def api_add_todo(todo: TodoCreate):
    with get_db() as conn:
        cursor = conn.execute(
            'INSERT INTO todos (task, priority) VALUES (?, ?)', (todo.task, todo.priority))
        todo_id = cursor.lastrowid
        conn.commit()

    return {'id': todo_id, 'message': 'Task created successfully'}


@app.delete('/api/todos/{todo_id}')
def api_delete_todo(todo_id: int):
    with get_db() as conn:
        todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                            (todo_id,)).fetchone()

        if not todo:
            raise HTTPException(status_code=404, detail='Task not found')

        conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
        conn.commit()

    return {'message': 'Task deleted successfully'}


@app.get('/stats')
def stats(request: Request):
    with get_db() as conn:
        total = conn.execute(
            'SELECT COUNT(*) as count FROM todos').fetchone()['count']
        completed = conn.execute(
            'SELECT COUNT(*) as count FROM todos WHERE completed = 1').fetchone()['count']
        pending = total - completed

        priority_stats = conn.execute('''
            SELECT priority, COUNT(*) as count
            FROM todos
            GROUP BY priority
        ''').fetchall()

    return templates.TemplateResponse('stats.html', {
        'request': request,
        'total': total,
        'completed': completed,
        'pending': pending,
        'priority_stats': priority_stats,
        'messages': get_flashed_messages(request),
    })


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5000)
