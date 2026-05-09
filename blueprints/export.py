"""Blueprint: Export 数据导出"""
import csv
import io
from flask import Blueprint, redirect, url_for, session, flash, Response
from blueprints.decorators import login_required

export_bp = Blueprint('export', __name__)


@export_bp.route('/export/<format>')
@login_required
def export_data(format):
    from app import get_db
    db = get_db()
    uid = session['user_id']

    if format == 'study':
        rows = db.execute('''
            SELECT sr.study_date, sr.duration_minutes, c.name as course_name
            FROM study_records sr LEFT JOIN courses c ON sr.course_id = c.id
            WHERE sr.user_id=? ORDER BY sr.study_date DESC
        ''', (uid,)).fetchall()
        filename = 'study_records.csv'
        headers = ['日期', '时长(分钟)', '课程']
        data_rows = [[r['study_date'], r['duration_minutes'], r['course_name'] or ''] for r in rows]
    elif format == 'tasks':
        rows = db.execute('''
            SELECT t.title, t.description, t.priority, t.status, t.due_date, t.tags,
                   c.name as course_name, t.created_at, t.completed_at
            FROM tasks t LEFT JOIN courses c ON t.course_id = c.id
            WHERE t.user_id=? ORDER BY t.created_at DESC
        ''', (uid,)).fetchall()
        filename = 'tasks.csv'
        headers = ['任务', '描述', '优先级', '状态', '截止日期', '标签', '课程', '创建时间', '完成时间']
        priority_map = {1: '紧急', 2: '一般', 3: '不急', 4: '低优'}
        status_map = {'todo': '待办', 'doing': '进行中', 'done': '已完成'}
        data_rows = [[r['title'], r['description'], priority_map.get(r['priority'], ''),
                       status_map.get(r['status'], ''), r['due_date'] or '', r['tags'] or '',
                       r['course_name'] or '', r['created_at'] or '', r['completed_at'] or ''] for r in rows]
    elif format == 'pomodoro':
        rows = db.execute('''
            SELECT p.duration, p.started_at, t.title as task_title
            FROM pomodoro_sessions p LEFT JOIN tasks t ON p.task_id = t.id
            WHERE p.user_id=? ORDER BY p.started_at DESC
        ''', (uid,)).fetchall()
        filename = 'pomodoro.csv'
        headers = ['时长(分钟)', '开始时间', '关联任务']
        data_rows = [[r['duration'], r['started_at'] or '', r['task_title'] or ''] for r in rows]
    else:
        flash('未知导出类型', 'error')
        return redirect(url_for('stats.stats'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data_rows:
        writer.writerow(row)
    csv_content = '\ufeff' + output.getvalue()
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )
