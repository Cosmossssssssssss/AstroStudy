"""Blueprint: Search 全局搜索"""
from flask import Blueprint, render_template, request, session
from blueprints.decorators import login_required

search_bp = Blueprint('search', __name__)


@search_bp.route('/search')
@login_required
def search():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    q = request.args.get('q', '').strip()
    if not q:
        return render_template('search.html', q=q, tasks=[], courses=[], exams=[])
    like = f'%{q}%'
    tasks_r = db.execute('''
        SELECT t.*, c.name as course_name, c.color as course_color
        FROM tasks t LEFT JOIN courses c ON t.course_id = c.id
        WHERE t.user_id=? AND (t.title LIKE ? OR t.description LIKE ? OR t.tags LIKE ?)
        ORDER BY t.created_at DESC LIMIT 20
    ''', (uid, like, like, like)).fetchall()
    courses_r = db.execute(
        'SELECT * FROM courses WHERE user_id=? AND name LIKE ? ORDER BY name', (uid, like)
    ).fetchall()
    exams_r = db.execute('''
        SELECT e.*, c.name as course_name, c.color as course_color
        FROM exams e LEFT JOIN courses c ON e.course_id = c.id
        WHERE e.user_id=? AND (e.name LIKE ? OR e.notes LIKE ?)
        ORDER BY e.exam_date ASC LIMIT 20
    ''', (uid, like, like)).fetchall()
    return render_template('search.html', q=q, tasks=tasks_r, courses=courses_r, exams=exams_r)
