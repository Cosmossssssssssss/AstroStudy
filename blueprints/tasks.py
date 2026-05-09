"""
Blueprint: Tasks 任务管理
路由：/tasks, /tasks/add, /tasks/<id>/toggle, /tasks/<id>/delete,
      /api/tasks/reorder, /api/tasks/<id>/soft-delete, /api/tasks/restore
"""
from datetime import datetime, date, timedelta
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from blueprints.decorators import login_required
from blueprints.utils import safe_int, safe_route

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks')
@login_required
def tasks():
    """任务列表：支持列表/看板/日历三种视图，标签筛选"""
    from app import get_db
    db = get_db()
    uid = session['user_id']
    view = request.args.get('view', 'list')
    filter_course = request.args.get('course_id')
    default_status = 'all' if view == 'calendar' else 'todo'
    filter_status = request.args.get('status', default_status)

    query = '''
        SELECT t.*, c.name as course_name, c.color as course_color
        FROM tasks t LEFT JOIN courses c ON t.course_id = c.id
        WHERE t.user_id=?
    '''
    params = [uid]

    if filter_course:
        query += ' AND t.course_id=?'
        params.append(filter_course)
    if filter_status and filter_status != 'all':
        query += ' AND t.status=?'
        params.append(filter_status)

    query += ' ORDER BY t.sort_order ASC, t.priority ASC, t.due_date ASC, t.created_at DESC'
    task_list = db.execute(query, params).fetchall()

    courses_list = db.execute(
        'SELECT * FROM courses WHERE user_id=? ORDER BY name', (uid,)
    ).fetchall()

    # Get all unique tags
    all_tags_raw = db.execute(
        "SELECT tags FROM tasks WHERE user_id=? AND tags!=''", (uid,)
    ).fetchall()
    all_tags = set()
    for row in all_tags_raw:
        for tag in row['tags'].split(','):
            tag = tag.strip()
            if tag:
                all_tags.add(tag)

    # Calendar data
    cal_year = int(request.args.get('y', date.today().year))
    cal_month = int(request.args.get('m', date.today().month))
    first_day = date(cal_year, cal_month, 1)
    if cal_month == 12:
        last_day = date(cal_year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(cal_year, cal_month + 1, 1) - timedelta(days=1)
    first_weekday = first_day.weekday()  # 0=Mon

    # Build calendar weeks
    cal_weeks = []
    current_week = [None] * first_weekday
    for d in range(1, last_day.day + 1):
        current_date = date(cal_year, cal_month, d)
        date_str = current_date.isoformat()
        day_tasks = [t for t in task_list if (t['due_date'] and str(t['due_date'])[:10] == date_str) or (not t['due_date'] and t['created_at'] and str(t['created_at'])[:10] == date_str)]
        current_week.append({
            'day': d,
            'date': date_str,
            'is_today': current_date == date.today(),
            'tasks': day_tasks
        })
        if len(current_week) == 7:
            cal_weeks.append(current_week)
            current_week = []
    if current_week:
        while len(current_week) < 7:
            current_week.append(None)
        cal_weeks.append(current_week)

    # Month navigation
    if cal_month == 1:
        prev_month, prev_year = 12, cal_year - 1
    else:
        prev_month, prev_year = cal_month - 1, cal_year
    if cal_month == 12:
        next_month, next_year = 1, cal_year + 1
    else:
        next_month, next_year = cal_month + 1, cal_year

    return render_template('tasks.html',
        tasks=task_list, courses=courses_list, view=view,
        filter_course=filter_course, filter_status=filter_status,
        all_tags=sorted(all_tags),
        cal_weeks=cal_weeks, cal_year=cal_year, cal_month=cal_month,
        prev_m=prev_month, prev_y=prev_year,
        next_m=next_month, next_y=next_year
    )


@tasks_bp.route('/tasks/add', methods=['POST'])
@login_required
@safe_route
def add_task():
    from app import get_db
    db = get_db()
    title = request.form['title'].strip()
    priority = safe_int(request.form.get('priority')) or 2
    due_date = request.form.get('due_date') or None
    course_id = safe_int(request.form.get('course_id'))
    if course_id:
        exists = db.execute(
            'SELECT 1 FROM courses WHERE id=? AND user_id=?',
            (course_id, session['user_id'])
        ).fetchone()
        if not exists:
            course_id = None
    description = request.form.get('description', '').strip()
    tags = request.form.get('tags', '').strip()
    if title:
        max_order = db.execute(
            'SELECT COALESCE(MAX(sort_order), 0) as m FROM tasks WHERE user_id=?',
            (session['user_id'],)
        ).fetchone()['m']
        db.execute(
            'INSERT INTO tasks (title, description, priority, due_date, course_id, tags, sort_order, user_id) VALUES (?,?,?,?,?,?,?,?)',
            (title, description, priority, due_date, course_id, tags, max_order + 1, session['user_id'])
        )
        db.commit()
    return redirect(request.referrer or url_for('tasks.tasks'))


@tasks_bp.route('/tasks/<int:id>/toggle', methods=['POST'])
@login_required
@safe_route
def toggle_task(id):
    from app import get_db
    db = get_db()
    task = db.execute(
        'SELECT * FROM tasks WHERE id=? AND user_id=?', (id, session['user_id'])
    ).fetchone()
    if task:
        new_status = 'done' if task['status'] != 'done' else 'todo'
        completed_at = datetime.now().isoformat() if new_status == 'done' else None
        db.execute(
            'UPDATE tasks SET status=?, completed_at=? WHERE id=?',
            (new_status, completed_at, id)
        )
        db.commit()
    return redirect(request.referrer or url_for('tasks.tasks'))


@tasks_bp.route('/tasks/<int:id>/delete', methods=['POST'])
@login_required
@safe_route
def delete_task(id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM tasks WHERE id=? AND user_id=?', (id, session['user_id']))
    db.commit()
    return redirect(url_for('tasks.tasks'))


@tasks_bp.route('/api/tasks/reorder', methods=['POST'])
@login_required
def reorder_tasks():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    data = request.get_json()
    order = data.get('order', [])
    for i, task_id in enumerate(order):
        db.execute('UPDATE tasks SET sort_order=? WHERE id=? AND user_id=?', (i, task_id, uid))
    db.commit()
    return jsonify({'ok': True})


@tasks_bp.route('/api/tasks/<int:id>/soft-delete', methods=['POST'])
@login_required
def soft_delete_task(id):
    """Returns the task data so client can show undo toast"""
    from app import get_db
    db = get_db()
    task = db.execute(
        'SELECT * FROM tasks WHERE id=? AND user_id=?', (id, session['user_id'])
    ).fetchone()
    if not task:
        return jsonify({'error': 'not found'}), 404
    task_data = dict(task)
    db.execute('DELETE FROM tasks WHERE id=? AND user_id=?', (id, session['user_id']))
    db.commit()
    return jsonify({'ok': True, 'task': task_data})


@tasks_bp.route('/api/tasks/restore', methods=['POST'])
@login_required
def restore_task():
    """Restore a deleted task"""
    from app import get_db
    db = get_db()
    data = request.get_json()
    t = data.get('task', {})
    if t.get('title'):
        max_order = db.execute(
            'SELECT COALESCE(MAX(sort_order), 0) as m FROM tasks WHERE user_id=?',
            (session['user_id'],)
        ).fetchone()['m']
        db.execute(
            'INSERT INTO tasks (title, description, priority, status, due_date, course_id, tags, sort_order, user_id, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (t['title'], t.get('description',''), t.get('priority',2), t.get('status','todo'),
             t.get('due_date'), t.get('course_id'), t.get('tags',''), max_order+1,
             session['user_id'], t.get('completed_at'))
        )
        db.commit()
        return jsonify({'ok': True})
    return jsonify({'error': 'missing title'}), 400
