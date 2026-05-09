"""Blueprint: Exams 考试管理"""
from flask import Blueprint, render_template, request, redirect, url_for, session
from blueprints.decorators import login_required
from blueprints.utils import safe_int, safe_route

exams_bp = Blueprint('exams', __name__)


@exams_bp.route('/exams')
@login_required
def exams():
    from app import get_db
    from datetime import date
    db = get_db()
    uid = session['user_id']
    today = date.today().isoformat()
    exam_list = db.execute('''
        SELECT e.*, c.name as course_name, c.color as course_color,
               CAST(julianday(e.exam_date) - julianday(?) AS INTEGER) as days_left
        FROM exams e LEFT JOIN courses c ON e.course_id = c.id
        WHERE e.user_id=? ORDER BY e.exam_date ASC
    ''', (today, uid)).fetchall()
    courses_list = db.execute(
        'SELECT * FROM courses WHERE user_id=? ORDER BY name', (uid,)
    ).fetchall()
    return render_template('exams.html', exams=exam_list, courses=courses_list)


@exams_bp.route('/exams/add', methods=['POST'])
@login_required
@safe_route
def add_exam():
    from app import get_db
    db = get_db()
    name = request.form['name'].strip()
    exam_date = request.form['exam_date']
    location = request.form.get('location', '').strip()
    notes = request.form.get('notes', '').strip()
    course_id = safe_int(request.form.get('course_id'))
    if course_id:
        exists = db.execute('SELECT 1 FROM courses WHERE id=? AND user_id=?', (course_id, session['user_id'])).fetchone()
        if not exists:
            course_id = None
    if name and exam_date:
        db.execute(
            'INSERT INTO exams (name, exam_date, location, notes, course_id, user_id) VALUES (?,?,?,?,?,?)',
            (name, exam_date, location, notes, course_id, session['user_id'])
        )
        db.commit()
    return redirect(url_for('exams.exams'))


@exams_bp.route('/exams/<int:id>/delete', methods=['POST'])
@login_required
@safe_route
def delete_exam(id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM exams WHERE id=? AND user_id=?', (id, session['user_id']))
    db.commit()
    return redirect(url_for('exams.exams'))
