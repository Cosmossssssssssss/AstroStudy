"""
Blueprint 共享装饰器
login_required: 登录验证装饰器，无 app 依赖
"""
from functools import wraps
from flask import session, redirect, url_for


def login_required(f):
    """登录验证装饰器，未登录时重定向到登录页"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
