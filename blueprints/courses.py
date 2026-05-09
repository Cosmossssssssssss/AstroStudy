"""
Blueprint: Courses 课程管理
路由：/courses, /courses/add, /courses/<id>/delete, /semesters/add
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, session
)
from blueprints.decorators import login_required
from blueprints.utils import safe_int, safe_route

courses_bp = Blueprint('courses', __name__)


@courses_bp.route('/courses')
@login_required
def courses():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    course_list = db.execute('''
        SELECT c.*, s.name as semester_name,
            (SELECT COUNT(*) FROM tasks WHERE course_id=c.id AND status!='done') as task_count
        FROM courses c LEFT JOIN semesters s ON c.semester_id = s.id
        WHERE c.user_id=? ORDER BY c.name
    ''', (uid,)).fetchall()
    semesters = db.execute(
        'SELECT * FROM semesters WHERE user_id=? ORDER BY start_date DESC', (uid,)
    ).fetchall()
    return render_template('courses.html', courses=course_list, semesters=semesters)


@courses_bp.route('/courses/add', methods=['POST'])
@login_required
@safe_route
def add_course():
    from app import get_db
    db = get_db()
    name = request.form['name'].strip()
    color = request.form.get('color', '#4A90D9')
    semester_id = safe_int(request.form.get('semester_id'))
    if semester_id:
        exists = db.execute(
            'SELECT 1 FROM semesters WHERE id=? AND user_id=?',
            (semester_id, session['user_id'])
        ).fetchone()
        if not exists:
            semester_id = None
    if name:
        db.execute(
            'INSERT INTO courses (name, color, semester_id, user_id) VALUES (?,?,?,?)',
            (name, color, semester_id, session['user_id'])
        )
        db.commit()
    return redirect(url_for('courses.courses'))


@courses_bp.route('/courses/<int:id>/delete', methods=['POST'])
@login_required
@safe_route
def delete_course(id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM courses WHERE id=? AND user_id=?', (id, session['user_id']))
    db.commit()
    return redirect(url_for('courses.courses'))


@courses_bp.route('/semesters/add', methods=['POST'])
@login_required
def add_semester():
    from app import get_db
    db = get_db()
    name = request.form['name'].strip()
    start = request.form['start_date']
    end = request.form['end_date']
    if name and start and end:
        db.execute(
            'INSERT INTO semesters (name, start_date, end_date, user_id) VALUES (?,?,?,?)',
            (name, start, end, session['user_id'])
        )
        db.commit()
    return redirect(url_for('courses.courses'))
