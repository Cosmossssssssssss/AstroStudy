"""Blueprint: API 热力图、图表、每日签"""
import re
import uuid
from datetime import date, timedelta, datetime
from flask import Blueprint, request, session, jsonify
from blueprints.decorators import login_required

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/heatmap')
@login_required
def api_heatmap():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    end = date.today()
    start = end - timedelta(days=364)
    rows = db.execute('''
        SELECT study_date, SUM(duration_minutes) as minutes
        FROM study_records WHERE user_id=? AND study_date>=? AND study_date<=?
        GROUP BY study_date
    ''', (uid, start.isoformat(), end.isoformat())).fetchall()
    data = {row['study_date']: row['minutes'] for row in rows}
    result = []
    d = start
    while d <= end:
        result.append({'date': d.isoformat(), 'minutes': data.get(d.isoformat(), 0)})
        d += timedelta(days=1)
    return jsonify(result)


@api_bp.route('/api/study-week')
@login_required
def api_study_week():
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
        days.append({'date': d.strftime('%m/%d'), 'minutes': minutes})
    return jsonify(days)


# ─── Fortune 抽签 ────────────────────────────────────────────────────────

FORTUNE_DATA = [
    {
        'level': 1, 'name': '大吉', 'emoji': '🌟',
        'weight': 12, 'color': '#ff6b6b',
        'bg': 'linear-gradient(135deg, #ff6b6b, #ee5a24)',
        'texts': [
            '今日文思泉涌，宜攻克难题、整理笔记，收获满满！',
            '状态极佳的一天，刷题如有神助，效率翻倍！',
            '今日适合挑战高难度内容，突破就在眼前！',
            '灵感迸发，适合做创意类任务和深度学习。',
        ],
        'yi': ['刷题', '挑战高难度', '制定长期计划', '竞赛训练', '学新知识', '吃火锅'],
        'buyi': ['翘课', '熬夜', '抄作业', '拖延', '抱怨人生'],
    },
    {
        'level': 2, 'name': '中吉', 'emoji': '✨',
        'weight': 20, 'color': '#f39c12',
        'bg': 'linear-gradient(135deg, #f39c12, #e67e22)',
        'texts': [
            '今日状态在线，适合查漏补缺、巩固基础。',
            '稳步前进的一天，复习旧知会有新收获。',
            '适合系统梳理知识点，构建完整知识框架。',
            '今日宜制定计划，按部就班效率高。',
        ],
        'yi': ['复习巩固', '系统梳理', '制定计划', '做笔记', '小组讨论', '吃烧烤'],
        'buyi': ['三心二意', '临时抱佛脚', '自我怀疑', '纠结过去'],
    },
    {
        'level': 3, 'name': '小吉', 'emoji': '🍀',
        'weight': 22, 'color': '#27ae60',
        'bg': 'linear-gradient(135deg, #27ae60, #2ecc71)',
        'texts': [
            '今日宜整理笔记、归纳总结，小步稳进。',
            '平稳踏实的一天，适合做练习题巩固。',
            '今日适合与同学讨论交流，互相学习进步。',
            '适合做错题回顾，把踩过的坑变成经验。',
        ],
        'yi': ['整理笔记', '错题回顾', '交流学习', '轻松复习', '适度运动', '喝奶茶'],
        'buyi': ['贪多嚼不烂', '独自硬撑', '过度焦虑', '空腹学习'],
    },
    {
        'level': 4, 'name': '吉', 'emoji': '🎋',
        'weight': 20, 'color': '#4A90D9',
        'bg': 'linear-gradient(135deg, #4A90D9, #6c5ce7)',
        'texts': [
            '今日宜按时作息，养精蓄锐后再战。',
            '适合做轻松的复习，不必强求进度。',
            '今日心态平和，适合慢节奏学习。',
            '小憩之后效率更高，适当运动有益学习。',
        ],
        'yi': ['按时作息', '轻松复习', '散步放松', '整理桌面', '做饭犒劳自己', '早睡'],
        'buyi': ['拼命刷题', '自我施压', '攀比进度', '深夜emo'],
    },
    {
        'level': 5, 'name': '末吉', 'emoji': '🌱',
        'weight': 14, 'color': '#8e44ad',
        'bg': 'linear-gradient(135deg, #8e44ad, #9b59b6)',
        'texts': [
            '今日虽有小波折，但坚持就是胜利！',
            '遇到难题别灰心，换个角度也许就通了。',
            '今日宜先做简单题热身，逐步进入状态。',
            '慢工出细活，今天适合打磨已有成果。',
        ],
        'yi': ['热身练习', '换个思路', '求助同学', '听音乐学习', '吃好吃的'],
        'buyi': ['放弃', '自暴自弃', '钻牛角尖', '硬撑到底'],
    },
    {
        'level': 6, 'name': '凶', 'emoji': '⚡',
        'weight': 9, 'color': '#e74c3c',
        'bg': 'linear-gradient(135deg, #e74c3c, #c0392b)',
        'texts': [
            '今日心绪浮动，不妨先做运动放松再学习。',
            '可能遇到瓶颈，暂时放下也许会有新思路。',
            '今日不宜强攻难题，回顾基础更有效。',
            '适当休息，明日再战精力更充沛！',
        ],
        'yi': ['运动放松', '回顾基础', '适当休息', '吃甜品', '和朋友聊天', '早点睡'],
        'buyi': ['硬攻难题', '熬夜冲刺', '自我否定', '作弊', '暴饮暴食'],
    },
    {
        'level': 7, 'name': '大凶', 'emoji': '🌩️',
        'weight': 3, 'color': '#2c3e50',
        'bg': 'linear-gradient(135deg, #2c3e50, #34495e)',
        'texts': [
            '今日诸事宜诚实踏实，投机取巧反受其害。',
            '做事宜谨慎，三思而后行，不宜冲动决策。',
            '今日宜韬光养晦，为明天积蓄力量。',
            '困难只是暂时的，调整心态明天会更好！',
        ],
        'yi': ['韬光养晦', '诚实踏实', '帮助别人', '吃顿好的', '整理心情'],
        'buyi': ['作弊', '冲动决策', '逃避问题', '自怨自艾', '和人吵架'],
    },
]


def generate_fortune(user_id):
    today_str = date.today().isoformat()
    import random
    rng = random.Random(f'{user_id}-{today_str}')
    weights = [f['weight'] for f in FORTUNE_DATA]
    total_w = sum(weights)
    r = rng.uniform(0, total_w)
    cumulative = 0
    chosen = FORTUNE_DATA[-1]
    for f in FORTUNE_DATA:
        cumulative += f['weight']
        if r <= cumulative:
            chosen = f
            break
    text = rng.choice(chosen['texts'])
    lucky_num = rng.randint(1, 99)
    # Pick 3 yi and 3 buyi
    yi_count = min(3, len(chosen['yi']))
    buyi_count = min(3, len(chosen['buyi']))
    yi_items = rng.sample(chosen['yi'], yi_count)
    buyi_items = rng.sample(chosen['buyi'], buyi_count)
    return {
        'level': chosen['level'], 'level_name': chosen['name'],
        'emoji': chosen['emoji'], 'color': chosen['color'], 'bg': chosen['bg'],
        'text': text, 'lucky_number': lucky_num,
        'yi': yi_items, 'buyi': buyi_items,
    }


@api_bp.route('/api/fortune', methods=['GET', 'POST'])
@login_required
def api_fortune():
    from app import get_db
    import json
    db = get_db()
    uid = session['user_id']
    today_str = date.today().isoformat()
    if request.method == 'POST':
        row = db.execute('SELECT * FROM daily_fortunes WHERE user_id=? AND fortune_date=?',
                         (uid, today_str)).fetchone()
        if row:
            db.execute('UPDATE daily_fortunes SET shown=1 WHERE user_id=? AND fortune_date=?',
                       (uid, today_str))
            db.commit()
            return jsonify({
                'ok': True, 'exists': True, 'shown': True,
                'level': row['level'], 'level_name': row['level_name'],
                'emoji': row['emoji'] if row['emoji'] else None, 'text': row['fortune_text'],
                'lucky_number': row['lucky_number'],
                'yi': json.loads(row['yi']) if row['yi'] else [],
                'buyi': json.loads(row['buyi']) if row['buyi'] else [],
                'color': row['color'] if row['color'] else None, 'bg': row['bg'] if row['bg'] else None,
            })
        fortune = generate_fortune(uid)
        db.execute(
            'INSERT INTO daily_fortunes (user_id, fortune_date, level, level_name, emoji, fortune_text, lucky_number, yi, buyi, color, bg, shown) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)',
            (uid, today_str, fortune['level'], fortune['level_name'], fortune['emoji'], fortune['text'],
             fortune['lucky_number'], json.dumps(fortune['yi'], ensure_ascii=False),
             json.dumps(fortune['buyi'], ensure_ascii=False), fortune['color'], fortune['bg'])
        )
        db.commit()
        return jsonify({'ok': True, 'exists': False, 'shown': True, **fortune})
    row = db.execute('SELECT * FROM daily_fortunes WHERE user_id=? AND fortune_date=?',
                     (uid, today_str)).fetchone()
    if row:
        return jsonify({
            'exists': True, 'shown': bool(row['shown']),
            'level': row['level'], 'level_name': row['level_name'],
            'emoji': row['emoji'] if row['emoji'] else None, 'text': row['fortune_text'],
            'lucky_number': row['lucky_number'],
            'yi': json.loads(row['yi']) if row['yi'] else [],
            'buyi': json.loads(row['buyi']) if row['buyi'] else [],
            'color': row['color'] if row['color'] else None, 'bg': row['bg'] if row['bg'] else None,
        })
    fortune = generate_fortune(uid)
    return jsonify({'exists': False, 'shown': False, **fortune})


@api_bp.route('/api/fortune/today')
@login_required
def api_fortune_today():
    from app import get_db
    import json
    db = get_db()
    uid = session['user_id']
    today_str = date.today().isoformat()
    row = db.execute('SELECT * FROM daily_fortunes WHERE user_id=? AND fortune_date=?',
                     (uid, today_str)).fetchone()
    if row:
        return jsonify({
            'exists': True, 'shown': bool(row['shown']),
            'level': row['level'], 'level_name': row['level_name'],
            'emoji': row['emoji'] if row['emoji'] else None, 'text': row['fortune_text'],
            'lucky_number': row['lucky_number'],
            'yi': json.loads(row['yi']) if row['yi'] else [],
            'buyi': json.loads(row['buyi']) if row['buyi'] else [],
            'color': row['color'] if row['color'] else None, 'bg': row['bg'] if row['bg'] else None,
        })
    return jsonify({'exists': False})


# ─── Achievement Utilities ───

def check_achievements(db, uid):
    """Check and unlock any new achievements for user. Returns list of newly unlocked."""
    newly = []
    today = date.today()

    # Counts
    pc = db.execute('SELECT COUNT(*) as c FROM pomodoro_sessions WHERE user_id=?',(uid,)).fetchone()['c']
    nc = db.execute('SELECT COUNT(*) as c FROM notes WHERE user_id=?',(uid,)).fetchone()['c']
    tc = db.execute(
        "SELECT COUNT(*) as c FROM tasks WHERE user_id=? AND status='done'",(uid,)
    ).fetchone()['c']
    all_three = 1 if (pc>0 and nc>0 and tc>0) else 0

    # Streak
    rows = db.execute('''
        SELECT DISTINCT date(started_at) as d FROM pomodoro_sessions WHERE user_id=?
        ORDER BY d DESC
    ''',(uid,)).fetchall()
    streak = 0
    today_row = db.execute(
        'SELECT 1 FROM pomodoro_sessions WHERE user_id=? AND date(started_at)=?',
        (uid, today.isoformat())
    ).fetchone()
    check_date = today - timedelta(days=1) if today_row else today
    if today_row: streak = 1
    for r in rows:
        rd = date.fromisoformat(r['d'])
        if rd == check_date:
            streak += 1
            check_date = rd - timedelta(days=1)
        elif rd < check_date:
            break

    # Early morning
    em = db.execute(
        "SELECT 1 FROM pomodoro_sessions WHERE user_id=? AND time(started_at) < '07:00'",
        (uid,)
    ).fetchone()
    early_morning = 1 if em else 0

    values = {
        'pomodoro_count': pc, 'note_count': nc, 'task_count': tc,
        'streak_days': streak, 'all_three': all_three, 'early_morning': early_morning,
    }
    # Check each achievement
    all_achs = db.execute('SELECT * FROM achievements').fetchall()
    unlocked = {r['achievement_id'] for r in db.execute(
        'SELECT achievement_id FROM user_achievements WHERE user_id=?',(uid,)
    ).fetchall()}
    for a in all_achs:
        if a['id'] in unlocked:
            continue
        if values.get(a['criteria_type'], 0) >= a['criteria_value']:
            try:
                db.execute('INSERT INTO user_achievements (user_id,achievement_id) VALUES (?,?)',(uid,a['id']))
                newly.append(dict(a))
            except:
                pass
    if newly:
        db.commit()
    return newly


@api_bp.route('/api/achievements')
@login_required
def api_achievements():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    all_achs = db.execute('SELECT * FROM achievements ORDER BY id').fetchall()
    hints = {
        'milestone': '迈出第一步就会有惊喜 ✨',
        'volume': '坚持积累，水到渠成 🏆',
        'streak': '每天来打卡试试吧 📅',
        'explore': '在某个不经意的瞬间... 🌟'
    }
    unlocked = {r['achievement_id']: r['unlocked_at'] for r in db.execute(
        'SELECT achievement_id, unlocked_at FROM user_achievements WHERE user_id=?',(uid,)
    ).fetchall()}
    return jsonify([{
        'id': a['id'], 'name': a['name'], 'description': a['description'],
        'icon': a['icon'], 'points': a['points'], 'category': a['category'],
        'hint': hints.get(a['category'], ''),
        'unlocked': a['id'] in unlocked,
        'unlocked_at': unlocked.get(a['id'], None),
    } for a in all_achs])


@api_bp.route('/api/achievements/check', methods=['POST'])
@login_required
def api_achievements_check():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    newly = check_achievements(db, uid)
    return jsonify({'new': newly, 'count': len(newly)})
