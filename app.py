import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

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

# Routes


@app.route('/')
def index():
    conn = get_db_connection()
    todos = conn.execute(
        'SELECT * FROM todos ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('index.html', todos=todos)


@app.route('/add', methods=['POST'])
def add_todo():
    task = request.form.get('task')
    priority = request.form.get('priority', 'medium')

    if not task:
        flash('Task cannot be empty!', 'error')
        return redirect(url_for('index'))

    if len(task) > 200:
        flash('Task is too long! Maximum 200 characters.', 'error')
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO todos (task, priority) VALUES (?, ?)', (task, priority))
    conn.commit()
    conn.close()

    flash('Task added successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/toggle/<int:todo_id>')
def toggle_todo(todo_id):
    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                        (todo_id,)).fetchone()

    if todo:
        new_status = not todo['completed']
        conn.execute('UPDATE todos SET completed = ? WHERE id = ?',
                     (new_status, todo_id))
        conn.commit()
        flash(f'Task {"completed" if new_status else "reopened"}!', 'success')
    else:
        flash('Task not found!', 'error')

    conn.close()
    return redirect(url_for('index'))


@app.route('/delete/<int:todo_id>')
def delete_todo(todo_id):
    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                        (todo_id,)).fetchone()

    if todo:
        conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
        conn.commit()
        flash('Task deleted successfully!', 'success')
    else:
        flash('Task not found!', 'error')

    conn.close()
    return redirect(url_for('index'))


@app.route('/edit/<int:todo_id>', methods=['GET', 'POST'])
def edit_todo(todo_id):
    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                        (todo_id,)).fetchone()

    if not todo:
        flash('Task not found!', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_task = request.form.get('task')
        new_priority = request.form.get('priority')

        if not new_task:
            flash('Task cannot be empty!', 'error')
            return render_template('edit.html', todo=todo)

        if len(new_task) > 200:
            flash('Task is too long! Maximum 200 characters.', 'error')
            return render_template('edit.html', todo=todo)

        conn.execute('UPDATE todos SET task = ?, priority = ? WHERE id = ?',
                     (new_task, new_priority, todo_id))
        conn.commit()
        conn.close()

        flash('Task updated successfully!', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit.html', todo=todo)

# API Routes for testing


@app.route('/api/todos', methods=['GET'])
def api_get_todos():
    conn = get_db_connection()
    todos = conn.execute(
        'SELECT * FROM todos ORDER BY created_at DESC').fetchall()
    conn.close()

    return jsonify([{
        'id': todo['id'],
        'task': todo['task'],
        'completed': bool(todo['completed']),
        'created_at': todo['created_at'],
        'priority': todo['priority']
    } for todo in todos])


@app.route('/api/todos', methods=['POST'])
def api_add_todo():
    data = request.get_json()

    if not data or not data.get('task'):
        return jsonify({'error': 'Task is required'}), 400

    task = data['task']
    priority = data.get('priority', 'medium')

    if len(task) > 200:
        return jsonify({'error': 'Task too long'}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO todos (task, priority) VALUES (?, ?)', (task, priority))
    todo_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'id': todo_id, 'message': 'Task created successfully'}), 201


@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def api_delete_todo(todo_id):
    conn = get_db_connection()
    todo = conn.execute('SELECT * FROM todos WHERE id = ?',
                        (todo_id,)).fetchone()

    if not todo:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    conn.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Task deleted successfully'})


@app.route('/stats')
def stats():
    conn = get_db_connection()
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

    conn.close()

    return render_template('stats.html',
                           total=total,
                           completed=completed,
                           pending=pending,
                           priority_stats=priority_stats)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
