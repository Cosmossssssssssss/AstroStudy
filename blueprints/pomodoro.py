"""Blueprint: Pomodoro 番茄钟"""
from datetime import date
from flask import Blueprint, render_template, request, session, jsonify
from blueprints.decorators import login_required
from blueprints.utils import safe_int, safe_route
from blueprints.api import check_achievements

pomodoro_bp = Blueprint('pomodoro', __name__)


@pomodoro_bp.route('/pomodoro')
@login_required
def pomodoro():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    today = date.today().isoformat()
    today_sessions = db.execute('''
        SELECT p.*, t.title as task_title
        FROM pomodoro_sessions p LEFT JOIN tasks t ON p.task_id = t.id
        WHERE p.user_id=? AND date(p.started_at)=?
        ORDER BY p.started_at DESC
    ''', (uid, today)).fetchall()
    today_count = len(today_sessions)
    today_minutes = sum(s['duration'] for s in today_sessions)
    tasks_todo = db.execute(
        'SELECT * FROM tasks WHERE user_id=? AND status!=? ORDER BY priority',
        (uid, 'done')
    ).fetchall()
    return render_template('pomodoro.html',
        sessions=today_sessions, today_count=today_count,
        today_minutes=today_minutes, tasks=tasks_todo
    )


@pomodoro_bp.route('/pomodoro/complete', methods=['POST'])
@login_required
@safe_route
def pomodoro_complete():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    duration = safe_int(request.form.get('duration')) or 25
    task_id = safe_int(request.form.get('task_id'))
    if task_id:
        exists = db.execute('SELECT 1 FROM tasks WHERE id=? AND user_id=?', (task_id, uid)).fetchone()
        if not exists:
            task_id = None
    db.execute(
        'INSERT INTO pomodoro_sessions (duration, task_id, user_id) VALUES (?,?,?)',
        (duration, task_id, uid)
    )
    today = date.today().isoformat()
    course_id = None
    if task_id:
        task = db.execute('SELECT course_id FROM tasks WHERE id=?', (task_id,)).fetchone()
        if task:
            course_id = task['course_id']
    db.execute(
        'INSERT INTO study_records (study_date, duration_minutes, course_id, user_id) VALUES (?,?,?,?)',
        (today, duration, course_id, uid)
    )
    db.commit()
    newly = check_achievements(db, uid)
    return jsonify({'ok': True, 'achievements': newly})


@pomodoro_bp.route('/focus')
@login_required
def focus():
    """专注模式 - 全屏极简界面"""
    from app import get_db
    db = get_db()
    uid = session['user_id']
    today = date.today().isoformat()
    today_count = db.execute(
        'SELECT COUNT(*) as c FROM pomodoro_sessions WHERE user_id=? AND date(started_at)=?',
        (uid, today)
    ).fetchone()['c']
    today_minutes = db.execute(
        'SELECT COALESCE(SUM(duration),0) as m FROM pomodoro_sessions WHERE user_id=? AND date(started_at)=?',
        (uid, today)
    ).fetchone()['m']
    tasks = db.execute(
        'SELECT * FROM tasks WHERE user_id=? AND status!=? ORDER BY priority',
        (uid, 'done')
    ).fetchall()
    return render_template('focus.html',
        today_count=today_count, today_minutes=today_minutes, tasks=tasks)
