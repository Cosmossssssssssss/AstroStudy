"""Blueprint: Stats 统计"""
from datetime import date, timedelta
from flask import Blueprint, render_template, session
from blueprints.decorators import login_required

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/stats')
@login_required
def stats():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    days = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        minutes = db.execute(
            'SELECT COALESCE(SUM(duration_minutes), 0) as m FROM study_records WHERE user_id=? AND study_date=?',
            (uid, d.isoformat())
        ).fetchone()['m']
        days.append({'date': d.strftime('%m/%d'), 'weekday': d.strftime('%a'), 'minutes': minutes})
    course_stats = db.execute('''
        SELECT c.name, c.color, COALESCE(SUM(s.duration_minutes), 0) as total_minutes
        FROM study_records s JOIN courses c ON s.course_id = c.id
        WHERE s.user_id=? AND s.course_id IS NOT NULL
        GROUP BY s.course_id ORDER BY total_minutes DESC
    ''', (uid,)).fetchall()
    total_tasks = db.execute('SELECT COUNT(*) as c FROM tasks WHERE user_id=?', (uid,)).fetchone()['c']
    done_tasks = db.execute("SELECT COUNT(*) as c FROM tasks WHERE user_id=? AND status='done'", (uid,)).fetchone()['c']
    month_start = date.today().replace(day=1).isoformat()
    month_minutes = db.execute(
        'SELECT COALESCE(SUM(duration_minutes), 0) as m FROM study_records WHERE user_id=? AND study_date>=?',
        (uid, month_start)
    ).fetchone()['m']
    return render_template('stats.html',
        days=days, course_stats=course_stats,
        total_tasks=total_tasks, done_tasks=done_tasks,
        month_minutes=month_minutes
    )
