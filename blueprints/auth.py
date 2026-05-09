"""
Blueprint: Auth 用户认证
路由：/login, /register, /logout
支持邮箱或用户名登录 + 用户名+邮箱+密码注册
"""
import re
import sqlite3
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash
)

auth_bp = Blueprint('auth', __name__)

EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def _is_email(s):
    return bool(EMAIL_RE.match(s))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        from app import get_db
        identity = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        if _is_email(identity):
            user = db.execute(
                'SELECT * FROM users WHERE email=? AND password=?',
                (identity, password)
            ).fetchone()
        else:
            user = db.execute(
                'SELECT * FROM users WHERE username=? AND password=?',
                (identity, password)
            ).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误', 'error')
    return render_template('login.html', active_panel='login')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        from app import get_db
        username = request.form['username'].strip()
        email = request.form.get('email', '').strip()
        password = request.form['password']
        # Validate
        if not username or len(username) < 2:
            flash('用户名至少 2 个字符', 'error')
            return redirect(url_for('auth.register'))
        if not email or not _is_email(email):
            flash('请输入有效的邮箱地址', 'error')
            return redirect(url_for('auth.register'))
        if not password or len(password) < 3:
            flash('密码至少 3 个字符', 'error')
            return redirect(url_for('auth.register'))
        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, password)
            )
            db.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('auth.login'))
        except sqlite3.IntegrityError:
            flash('用户名或邮箱已存在', 'error')
    return render_template('register.html', active_panel='register')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
