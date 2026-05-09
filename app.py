"""
AstroStudy - 学习备考助手

一款简洁高效的学习备考管理工具，包含以下功能模块：
1. 用户系统：注册、登录、个人中心
2. 课程管理：课程 CRUD、学期分组
3. 任务管理：列表/看板/日历三视图、拖拽排序、标签系统
4. 笔记系统：Markdown 编辑器、块级内容模型、双向链接 [[wiki-links]]、标签属性、课程关联、闪卡复习
5. 番茄钟：自定义时长、休息提醒、关联任务
6. 考试管理：倒计时、关联课程
7. 学习统计：柱状图、热力图、课程分布、数据导出
8. 数据导出：CSV 格式，支持学习记录/任务/番茄钟导出

技术栈：Python Flask + SQLite + Bootstrap 5 + marked.js
"""
import os
import sys
import re
import uuid
import sqlite3
import csv
import io
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, g
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Support PyInstaller bundled exe
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, 'studyplanner.db')

# ─── Blueprint Registration ─────────────────────────────────────────
from blueprints.auth import auth_bp
from blueprints.courses import courses_bp
from blueprints.tasks import tasks_bp
from blueprints.exams import exams_bp
from blueprints.pomodoro import pomodoro_bp
from blueprints.stats import stats_bp
from blueprints.profile import profile_bp
from blueprints.notes import notes_bp
from blueprints.search import search_bp
from blueprints.export import export_bp
from blueprints.api import api_bp
app.register_blueprint(auth_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(exams_bp)
app.register_blueprint(pomodoro_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(search_bp)
app.register_blueprint(export_bp)
app.register_blueprint(api_bp)

# ─── Database 数据库模块 ───────────────────────────────────────────────

def get_db():
    """获取数据库连接，每个请求复用同一个连接（Flask g 对象）"""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        # Foreign keys disabled: LEFT JOIN handles missing references,
        # and stale form IDs won't crash the app
    return g.db

@app.after_request
def add_no_cache(response):
    # 只对 HTML 页面禁用缓存，静态资源允许浏览器缓存
    ct = response.content_type or ''
    if 'text/html' in ct:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.teardown_appcontext
def close_db(exc):
    """请求结束时关闭数据库连接"""
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    """初始化数据库，创建所有表结构（IF NOT EXISTS）"""
    db = sqlite3.connect(DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color TEXT DEFAULT '#4A90D9',
            semester_id INTEGER,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (semester_id) REFERENCES semesters(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority INTEGER DEFAULT 2,
            status TEXT DEFAULT 'todo',
            due_date DATE,
            course_id INTEGER,
            tags TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            exam_date DATE NOT NULL,
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            course_id INTEGER,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duration INTEGER NOT NULL DEFAULT 25,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_id INTEGER,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS study_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_date DATE NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            course_id INTEGER,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            markdown TEXT DEFAULT '',
            course_id INTEGER,
            folder_id INTEGER,
            pinned INTEGER DEFAULT 0,
            favorited INTEGER DEFAULT 0,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
            FOREIGN KEY (folder_id) REFERENCES note_folders(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS note_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES note_folders(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS note_blocks (
            id TEXT PRIMARY KEY,
            note_id INTEGER NOT NULL,
            block_type TEXT NOT NULL DEFAULT 'paragraph',
            content TEXT DEFAULT '',
            markdown TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            parent_id TEXT,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES note_blocks(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS note_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_note_id INTEGER NOT NULL,
            source_block_id TEXT,
            target_note_id INTEGER NOT NULL,
            link_text TEXT DEFAULT '',
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (source_block_id) REFERENCES note_blocks(id) ON DELETE CASCADE,
            FOREIGN KEY (target_note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            tag_name TEXT NOT NULL,
            tag_value TEXT DEFAULT '',
            user_id INTEGER NOT NULL,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            block_id TEXT,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            ease_factor REAL DEFAULT 2.5,
            interval_days REAL DEFAULT 0,
            repetitions INTEGER DEFAULT 0,
            next_review DATE,
            last_review DATE,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (block_id) REFERENCES note_blocks(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_note_blocks_note ON note_blocks(note_id);
        CREATE INDEX IF NOT EXISTS idx_note_links_source ON note_links(source_note_id);
        CREATE INDEX IF NOT EXISTS idx_note_links_target ON note_links(target_note_id);
        CREATE INDEX IF NOT EXISTS idx_note_tags_note ON note_tags(note_id);
        CREATE INDEX IF NOT EXISTS idx_flashcards_review ON flashcards(next_review, user_id);
        CREATE TABLE IF NOT EXISTS daily_fortunes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fortune_date DATE NOT NULL,
            level INTEGER NOT NULL,
            level_name TEXT NOT NULL,
            fortune_text TEXT NOT NULL,
            lucky_number INTEGER NOT NULL,
            shown INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, fortune_date)
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT DEFAULT '🏆',
            points INTEGER DEFAULT 10,
            category TEXT DEFAULT 'milestone',
            criteria_type TEXT NOT NULL,
            criteria_value INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_id INTEGER NOT NULL,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (achievement_id) REFERENCES achievements(id),
            UNIQUE(user_id, achievement_id)
        );
    ''')
    # 迁移：为已有的 notes 表添加新字段
    try:
        db.execute('ALTER TABLE notes ADD COLUMN folder_id INTEGER REFERENCES note_folders(id) ON DELETE SET NULL')
    except:
        pass
    try:
        db.execute('ALTER TABLE notes ADD COLUMN favorited INTEGER DEFAULT 0')
    except:
        pass
    db.commit()
    # Fortune table migration: add yi, buyi, emoji, color, bg columns
    for col in ['yi', 'buyi', 'emoji', 'color', 'bg']:
        try:
            db.execute(f'ALTER TABLE daily_fortunes ADD COLUMN {col} TEXT')
        except:
            pass
    db.execute("DELETE FROM daily_fortunes WHERE yi IS NULL")
    db.commit()
    # Seed achievements
    db.executescript('''
        INSERT OR IGNORE INTO achievements (id,name,description,icon,points,category,criteria_type,criteria_value) VALUES
        ( 1,'初次专注','完成第 1 个番茄钟','🍅',10,'milestone','pomodoro_count',1),
        ( 2,'番茄新手','累计完成 10 个番茄钟','⏱️',20,'volume','pomodoro_count',10),
        ( 3,'番茄达人','累计完成 50 个番茄钟','🍕',50,'volume','pomodoro_count',50),
        ( 4,'番茄大师','累计完成 100 个番茄钟','👑',100,'volume','pomodoro_count',100),
        ( 5,'连续七天','连续 7 天打卡学习','🔥',40,'streak','streak_days',7),
        ( 6,'月度战士','连续 30 天打卡学习','💪',90,'streak','streak_days',30),
        ( 7,'笔耕不辍','创建第 1 条笔记','📝',10,'milestone','note_count',1),
        ( 8,'笔记达人','累计创建 20 条笔记','📚',30,'volume','note_count',20),
        ( 9,'任务收割','完成第 1 个任务','✅',10,'milestone','task_count',1),
        (10,'效率王者','完成 10 个任务','⚡',30,'volume','task_count',10),
        (11,'三好学生','同时拥有番茄+笔记+任务记录','🌟',50,'explore','all_three',1),
        (12,'早鸟打卡','早上 7 点前完成 1 个番茄','🌅',30,'explore','early_morning',1);
    ''')
    # Migration: add email column to existing databases
    try:
        db.execute('ALTER TABLE users ADD COLUMN email TEXT')
        db.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    db.commit()
    db.close()

# ─── Auth 用户认证（已拆分至 blueprints/auth.py）────────────────────────────
from blueprints.decorators import login_required

# ─── Dashboard 首页模块 ──────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    """首页：今日任务、考试倒计时、学习统计、连续天数"""
    db = get_db()
    uid = session['user_id']
    today = date.today().isoformat()

    # 今日任务
    today_tasks = db.execute('''
        SELECT t.*, c.name as course_name, c.color as course_color
        FROM tasks t LEFT JOIN courses c ON t.course_id = c.id
        WHERE t.user_id=? AND t.status != 'done'
          AND (t.due_date=? OR t.due_date IS NULL)
        ORDER BY t.priority ASC, t.created_at DESC
    ''', (uid, today)).fetchall()

    # 即将到来的考试
    upcoming_exams_raw = db.execute('''
        SELECT e.*, c.name as course_name, c.color as course_color
        FROM exams e LEFT JOIN courses c ON e.course_id = c.id
        WHERE e.user_id=? AND e.exam_date >= ?
        ORDER BY e.exam_date ASC LIMIT 5
    ''', (uid, today)).fetchall()
    upcoming_exams = []
    for ex in upcoming_exams_raw:
        d = dict(ex)
        try:
            exam_dt = datetime.strptime(d['exam_date'][:10], '%Y-%m-%d').date()
            d['days_left'] = (exam_dt - date.today()).days
        except:
            d['days_left'] = 0
        upcoming_exams.append(d)

    # 本周学习时长
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_minutes = db.execute(
        'SELECT COALESCE(SUM(duration_minutes), 0) as total FROM study_records WHERE user_id=? AND study_date>=?',
        (uid, week_start)
    ).fetchone()['total']

    # 连续学习天数 (streak)
    streak = 0
    check_date = date.today()
    while True:
        has_record = db.execute(
            'SELECT 1 FROM study_records WHERE user_id=? AND study_date=? AND duration_minutes>0',
            (uid, check_date.isoformat())
        ).fetchone()
        if has_record:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            # 今天还没记录，从昨天开始算
            if check_date == date.today():
                check_date -= timedelta(days=1)
                continue
            break

    # 今日已学习分钟数
    today_minutes = db.execute(
        'SELECT COALESCE(SUM(duration_minutes), 0) as total FROM study_records WHERE user_id=? AND study_date=?',
        (uid, today)
    ).fetchone()['total']

    from blueprints.api import check_achievements
    newly_unlocked = check_achievements(db, uid)

    course_count = db.execute('SELECT COUNT(*) as cnt FROM courses WHERE user_id=?', (uid,)).fetchone()['cnt']

    return render_template('dashboard.html',
        today_tasks=today_tasks,
        upcoming_exams=upcoming_exams,
        week_minutes=week_minutes,
        streak=streak,
        today_minutes=today_minutes,
        today=date.today(),
        course_count=course_count
    )

import csv
import io

# Helper: safely convert form value to int or None
# ─── safe_int / safe_route（已拆分至 blueprints/utils.py）─────────────────
from blueprints.utils import safe_int, safe_route

# ─── Courses 课程管理（已拆分至 blueprints/courses.py）───────────────────

# ─── Tasks 任务管理（已拆分至 blueprints/tasks.py）───────────────────────

# ─── Exams（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Pomodoro（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Statistics（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Profile（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Notes（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Data（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Task Reorder / Soft Delete / Restore（已拆分至 blueprints/tasks.py）─────

# ─── Search（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Heatmap（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Daily（已拆分至 blueprints）──────────────────────────────────────────────────
# ─── Main 程序入口 ───────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    use_browser = '--browser' in sys.argv
    try:
        import webview
        if use_browser:
            raise ImportError  # 跳过 webview，走浏览器模式
        import threading
        url = 'http://127.0.0.1:5000'
        def start_flask():
            app.run(debug=False, port=5000, host='127.0.0.1')
        threading.Thread(target=start_flask, daemon=True).start()
        webview.create_window('AstroStudy v2.0.1', url, width=1200, height=800, min_size=(900, 600))
        webview.start()
    except ImportError:
        mode = '浏览器模式' if use_browser else 'Flask 开发模式'
        print(f'AstroStudy v2.0.1 启动中 ({mode})...')
        print('浏览器访问 http://127.0.0.1:5000')
        app.run(debug=True, port=5000, host='127.0.0.1')
