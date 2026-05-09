"""Blueprint: Profile 个人中心"""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from blueprints.decorators import login_required
import hashlib

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile')
@login_required
def profile():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    total_courses = db.execute('SELECT COUNT(*) as c FROM courses WHERE user_id=?', (uid,)).fetchone()['c']
    total_tasks = db.execute('SELECT COUNT(*) as c FROM tasks WHERE user_id=?', (uid,)).fetchone()['c']
    done_tasks = db.execute("SELECT COUNT(*) as c FROM tasks WHERE user_id=? AND status='done'", (uid,)).fetchone()['c']
    total_exams = db.execute('SELECT COUNT(*) as c FROM exams WHERE user_id=?', (uid,)).fetchone()['c']
    total_pomodoros = db.execute('SELECT COUNT(*) as c FROM pomodoro_sessions WHERE user_id=?', (uid,)).fetchone()['c']
    total_minutes = db.execute('SELECT COALESCE(SUM(duration_minutes), 0) as m FROM study_records WHERE user_id=?', (uid,)).fetchone()['m']
    total_hours = round(total_minutes / 60, 1)
    streak = 0
    check_date = date.today()
    while True:
        has = db.execute(
            'SELECT 1 FROM study_records WHERE user_id=? AND study_date=? AND duration_minutes>0',
            (uid, check_date.isoformat())
        ).fetchone()
        if has:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            if check_date == date.today():
                check_date -= timedelta(days=1)
                continue
            break
    # Generate consistent avatar gradient colors from username
    h = int(hashlib.md5(user['username'].encode()).hexdigest()[:8], 16)
    hue1 = h % 360
    hue2 = (hue1 + 40) % 360
    avatar_color1 = f'hsl({hue1}, 60%, 55%)'
    avatar_color2 = f'hsl({hue2}, 60%, 45%)'
    # Learning level
    levels = [(10, '🥉', '初学者', 1), (30, '🥈', '进阶者', 2), (50, '🥇', '勤奋学者', 3), (100, '🏅', '卷王', 4), (99999, '👑', '学神', 5)]
    level_emoji, level_name, level_num, level_next, level_pct = '👑', '学神', 5, 0, 100
    for th, em, nm, lv in levels:
        if total_hours < th:
            level_emoji, level_name, level_num, level_next = em, nm, lv, th
            prev_th = levels[lv - 2][0] if lv > 1 else 0
            level_pct = int((total_hours - prev_th) / (th - prev_th) * 100)
            break
    return render_template('profile.html',
        username=user['username'], created_at=user['created_at'],
        total_courses=total_courses, total_tasks=total_tasks, done_tasks=done_tasks,
        total_exams=total_exams, total_pomodoros=total_pomodoros,
        total_hours=total_hours, streak=streak,
        avatar_color1=avatar_color1, avatar_color2=avatar_color2,
        level_emoji=level_emoji, level_name=level_name, level_num=level_num,
        level_next=level_next, level_pct=level_pct
    )


@profile_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    old_pw = request.form['old_password']
    new_pw = request.form['new_password']
    confirm = request.form['confirm_password']
    user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if user['password'] != old_pw:
        flash('当前密码错误', 'error')
        return redirect(url_for('profile.profile'))
    if new_pw != confirm:
        flash('两次输入的新密码不一致', 'error')
        return redirect(url_for('profile.profile'))
    if len(new_pw) < 3:
        flash('新密码至少3个字符', 'error')
        return redirect(url_for('profile.profile'))
    db.execute('UPDATE users SET password=? WHERE id=?', (new_pw, uid))
    db.commit()
    flash('密码修改成功', 'success')
    return redirect(url_for('profile.profile'))


@profile_bp.route('/profile/reset', methods=['POST'])
@login_required
def reset_data():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    db.execute('DELETE FROM study_records WHERE user_id=?', (uid,))
    db.execute('DELETE FROM pomodoro_sessions WHERE user_id=?', (uid,))
    db.execute('DELETE FROM exams WHERE user_id=?', (uid,))
    db.execute('DELETE FROM tasks WHERE user_id=?', (uid,))
    db.execute('DELETE FROM courses WHERE user_id=?', (uid,))
    db.execute('DELETE FROM semesters WHERE user_id=?', (uid,))
    db.commit()
    flash('所有数据已清除', 'success')
    return redirect(url_for('profile.profile'))
