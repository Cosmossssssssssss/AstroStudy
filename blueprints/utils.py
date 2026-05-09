"""
Blueprint 共享工具函数
"""
import sqlite3
from functools import wraps
from flask import flash, redirect, request, url_for


def safe_int(val):
    """安全类型转换：表单值转整数，无效值返回 None"""
    if not val:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safe_route(f):
    """异常处理装饰器：捕获数据库错误，显示友好提示"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except sqlite3.IntegrityError as e:
            flash(f'数据完整性错误 ({f.__name__}): {e}', 'error')
            return redirect(request.referrer or url_for('dashboard'))
        except Exception as e:
            flash(f'操作失败 ({f.__name__}): {e}', 'error')
            return redirect(request.referrer or url_for('dashboard'))
    return wrapper
