"""Blueprint: Notes 笔记模块（含所有笔记路由+辅助函数+闪卡 API）"""
import re
import uuid
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from blueprints.decorators import login_required
from blueprints.utils import safe_int, safe_route

notes_bp = Blueprint('notes', __name__)


# ─── 辅助函数 ─────────────────────────────────────────────────────────────

def generate_block_id():
    return 'b' + uuid.uuid4().hex[:12]


def parse_blocks_from_markdown(markdown_text, note_id, user_id):
    if not markdown_text or not markdown_text.strip():
        return []
    lines = markdown_text.split('\n')
    blocks = []
    current_block_lines = []
    current_type = 'paragraph'
    sort_order = 0
    in_code = False
    in_math = False
    parent_stack = []

    def flush_block():
        nonlocal sort_order, current_block_lines, current_type
        content = '\n'.join(current_block_lines).strip()
        if content:
            blocks.append({
                'id': generate_block_id(), 'note_id': note_id,
                'block_type': current_type,
                'content': strip_markdown_syntax(content, current_type),
                'markdown': content, 'sort_order': sort_order,
                'parent_id': parent_stack[-1] if parent_stack else None,
                'user_id': user_id,
            })
            sort_order += 1
        current_block_lines = []
        current_type = 'paragraph'

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code:
                current_block_lines.append(line)
                current_type = 'code'
                flush_block()
                in_code = False
            else:
                if current_block_lines:
                    flush_block()
                in_code = True
                current_block_lines = [line]
                current_type = 'code'
            i += 1
            continue
        if in_code:
            current_block_lines.append(line)
            i += 1
            continue
        if stripped == '$$':
            if in_math:
                current_block_lines.append(line)
                current_type = 'math'
                flush_block()
                in_math = False
            else:
                if current_block_lines:
                    flush_block()
                in_math = True
                current_block_lines = [line]
                current_type = 'math'
            i += 1
            continue
        if in_math:
            current_block_lines.append(line)
            i += 1
            continue
        heading_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if heading_match:
            if current_block_lines:
                flush_block()
            level = len(heading_match.group(1))
            current_block_lines = [line]
            current_type = f'h{level}'
            flush_block()
            i += 1
            continue
        if re.match(r'^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]', stripped, re.IGNORECASE):
            if current_block_lines:
                flush_block()
            current_block_lines = [line]
            current_type = 'callout'
            i += 1
            while i < len(lines) and lines[i].strip().startswith('>'):
                current_block_lines.append(lines[i])
                i += 1
            flush_block()
            continue
        if stripped.startswith('>'):
            if current_type != 'quote':
                if current_block_lines:
                    flush_block()
                current_type = 'quote'
            current_block_lines.append(line)
            i += 1
            continue
        if re.match(r'^[-*+]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            if current_type != 'list_item':
                if current_block_lines:
                    flush_block()
                current_type = 'list_item'
            current_block_lines.append(line)
            i += 1
            continue
        if not stripped:
            if current_block_lines:
                flush_block()
            i += 1
            continue
        if current_type not in ('paragraph', 'quote', 'list_item'):
            if current_block_lines:
                flush_block()
            current_type = 'paragraph'
        current_block_lines.append(line)
        i += 1
    if current_block_lines:
        flush_block()
    return blocks


def strip_markdown_syntax(text, block_type):
    if block_type in ('code', 'math'):
        return text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    return text.strip()


def resolve_wiki_links(note_id, markdown_text, user_id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM note_links WHERE source_note_id=?', (note_id,))
    pattern = r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'
    for m in re.finditer(pattern, markdown_text):
        target = m.group(1).strip()
        display = m.group(2).strip() if m.group(2) else target
        target_note = db.execute('SELECT id FROM notes WHERE title=? AND user_id=?', (target, user_id)).fetchone()
        if target_note:
            db.execute(
                'INSERT INTO note_links (source_note_id, target_note_id, link_text, user_id) VALUES (?,?,?,?)',
                (note_id, target_note['id'], display, user_id)
            )
    db.commit()


def sync_note_blocks(note_id, markdown_text, user_id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM note_blocks WHERE note_id=?', (note_id,))
    blocks = parse_blocks_from_markdown(markdown_text, note_id, user_id)
    for b in blocks:
        db.execute(
            'INSERT INTO note_blocks (id, note_id, block_type, content, markdown, sort_order, parent_id, user_id) VALUES (?,?,?,?,?,?,?,?)',
            (b['id'], b['note_id'], b['block_type'], b['content'], b['markdown'], b['sort_order'], b['parent_id'], b['user_id'])
        )
    db.commit()
    resolve_wiki_links(note_id, markdown_text, user_id)
    return blocks


def get_backlinks(note_id, user_id):
    from app import get_db
    db = get_db()
    return db.execute('''
        SELECT DISTINCT n.id, n.title, nl.link_text
        FROM note_links nl JOIN notes n ON nl.source_note_id = n.id
        WHERE nl.target_note_id=? AND nl.user_id=? ORDER BY n.updated_at DESC
    ''', (note_id, user_id)).fetchall()


# ─── Tutorial Note ────────────────────────────────────────────────────

def create_tutorial_note(db, user_id):
    """Create a default tutorial note if user has no notes."""
    count = db.execute('SELECT COUNT(*) as c FROM notes WHERE user_id=?', (user_id,)).fetchone()['c']
    if count > 0:
        return
    import os as _os
    tut_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'templates', 'tutorial_content.md')
    try:
        with open(tut_path, 'r', encoding='utf-8') as f:
            tutorial_md = f.read().strip()
    except Exception:
        return
    title = '🎓 AstroStudy 使用指南'
    cursor = db.execute(
        'INSERT INTO notes (title, content, markdown, pinned, favorited, user_id) VALUES (?,?,?,1,1,?)',
        (title, tutorial_md, tutorial_md, user_id)
    )
    db.commit()
    note_id = cursor.lastrowid
    if note_id:
        sync_note_blocks(note_id, tutorial_md, user_id)

# ─── 笔记列表 ─────────────────────────────────────────────────────────────

@notes_bp.route('/notes')
@login_required
def notes():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    create_tutorial_note(db, uid)
    q = request.args.get('q', '').strip()
    course_filter = request.args.get('course', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    folder_filter = request.args.get('folder', '').strip()
    fav_filter = request.args.get('fav', '').strip()
    base_query = '''
        SELECT n.*, c.name as course_name, c.color as course_color, f.name as folder_name,
               (SELECT COUNT(*) FROM note_blocks nb WHERE nb.note_id = n.id) as block_count,
               (SELECT COUNT(*) FROM note_links nl WHERE nl.target_note_id = n.id) as backlink_count
        FROM notes n LEFT JOIN courses c ON n.course_id = c.id LEFT JOIN note_folders f ON n.folder_id = f.id WHERE n.user_id=?
    '''
    params = [uid]
    if q:
        like = f'%{q}%'
        base_query += ' AND (n.title LIKE ? OR n.content LIKE ? OR n.markdown LIKE ?)'
        params += [like, like, like]
    if course_filter:
        base_query += ' AND n.course_id = ?'
        params.append(int(course_filter))
    if tag_filter:
        base_query += ' AND EXISTS (SELECT 1 FROM note_tags nt WHERE nt.note_id = n.id AND nt.tag_name = ?)'
        params.append(tag_filter)
    if folder_filter:
        if folder_filter == 'none':
            base_query += ' AND n.folder_id IS NULL'
        else:
            base_query += ' AND n.folder_id = ?'
            params.append(int(folder_filter))
    if fav_filter:
        base_query += ' AND n.favorited = 1'
    base_query += ' ORDER BY n.pinned DESC, n.updated_at DESC'
    note_list = db.execute(base_query, params).fetchall()
    courses = db.execute('SELECT * FROM courses WHERE user_id=?', (uid,)).fetchall()
    all_tags = db.execute(
        'SELECT tag_name, COUNT(*) as cnt FROM note_tags WHERE user_id=? GROUP BY tag_name ORDER BY cnt DESC', (uid,)
    ).fetchall()
    folders = db.execute('SELECT id, name, parent_id FROM note_folders WHERE user_id=? ORDER BY name', (uid,)).fetchall()
    fav_count = db.execute('SELECT COUNT(*) as cnt FROM notes WHERE user_id=? AND favorited=1', (uid,)).fetchone()['cnt']
    return render_template('notes.html',
        notes=note_list, q=q, courses=courses, all_tags=all_tags,
        course_filter=course_filter, tag_filter=tag_filter,
        folders=folders, folder_filter=folder_filter, fav_filter=fav_filter, fav_count=fav_count
    )


# ─── CRUD ─────────────────────────────────────────────────────────────────

@notes_bp.route('/notes/add', methods=['POST'])
@login_required
@safe_route
def add_note():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    title = request.form['title'].strip()
    content = request.form.get('content', '').strip()
    course_id = request.form.get('course_id')
    folder_id = request.form.get('folder_id')
    course_id = int(course_id) if course_id else None
    folder_id = int(folder_id) if folder_id else None
    if title:
        cursor = db.execute(
            'INSERT INTO notes (title, content, markdown, course_id, folder_id, user_id) VALUES (?,?,?,?,?,?)',
            (title, content, content, course_id, folder_id, uid)
        )
        db.commit()
        note_id = cursor.lastrowid
        if content:
            sync_note_blocks(note_id, content, uid)
        return redirect(url_for('notes.note_detail', id=note_id))
    return redirect(url_for('notes.notes'))


@notes_bp.route('/notes/<int:id>/edit', methods=['POST'])
@login_required
@safe_route
def edit_note(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    title = request.form['title'].strip()
    content = request.form.get('content', '').strip()
    course_id = request.form.get('course_id')
    course_id = int(course_id) if course_id else None
    if title:
        db.execute(
            'UPDATE notes SET title=?, content=?, markdown=?, course_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',
            (title, content, content, course_id, id, uid)
        )
        db.commit()
        sync_note_blocks(id, content, uid)
    return redirect(url_for('notes.note_detail', id=id))


@notes_bp.route('/notes/<int:id>/delete', methods=['POST'])
@login_required
@safe_route
def delete_note(id):
    from app import get_db
    db = get_db()
    db.execute('DELETE FROM notes WHERE id=? AND user_id=?', (id, session['user_id']))
    db.commit()
    return redirect(url_for('notes.notes'))


@notes_bp.route('/notes/<int:id>/pin', methods=['POST'])
@login_required
@safe_route
def toggle_pin(id):
    from app import get_db
    db = get_db()
    note = db.execute('SELECT pinned FROM notes WHERE id=? AND user_id=?', (id, session['user_id'])).fetchone()
    if note:
        new = 0 if note['pinned'] else 1
        db.execute('UPDATE notes SET pinned=? WHERE id=?', (new, id))
        db.commit()
    return redirect(url_for('notes.notes'))


# ─── Favorites ────────────────────────────────────────────────────────────

@notes_bp.route('/notes/<int:id>/favorite', methods=['POST'])
@login_required
def toggle_favorite(id):
    from app import get_db
    db = get_db()
    note = db.execute('SELECT favorited FROM notes WHERE id=? AND user_id=?', (id, session['user_id'])).fetchone()
    if note:
        new = 0 if note['favorited'] else 1
        db.execute('UPDATE notes SET favorited=? WHERE id=?', (new, id))
        db.commit()
        return jsonify({'ok': True, 'favorited': bool(new)})
    return jsonify({'error': 'not found'}), 404


# ─── Folders ──────────────────────────────────────────────────────────────

@notes_bp.route('/api/folders', methods=['GET'])
@login_required
def get_folders():
    from app import get_db
    db = get_db()
    folders = db.execute('SELECT id, name, parent_id FROM note_folders WHERE user_id=? ORDER BY name', (session['user_id'],)).fetchall()
    return jsonify([dict(f) for f in folders])


@notes_bp.route('/api/folders', methods=['POST'])
@login_required
def create_folder():
    from app import get_db
    db = get_db()
    data = request.get_json()
    name = data.get('name', '').strip()
    parent_id = data.get('parent_id')
    if not name:
        return jsonify({'error': '名称不能为空'}), 400
    cursor = db.execute('INSERT INTO note_folders (name, parent_id, user_id) VALUES (?,?,?)', (name, parent_id, session['user_id']))
    db.commit()
    return jsonify({'ok': True, 'id': cursor.lastrowid, 'name': name})


@notes_bp.route('/api/folders/<int:id>', methods=['PUT'])
@login_required
def rename_folder(id):
    from app import get_db
    db = get_db()
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '名称不能为空'}), 400
    db.execute('UPDATE note_folders SET name=? WHERE id=? AND user_id=?', (name, id, session['user_id']))
    db.commit()
    return jsonify({'ok': True})


@notes_bp.route('/api/folders/<int:id>', methods=['DELETE'])
@login_required
def delete_folder(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    db.execute('UPDATE notes SET folder_id=NULL WHERE folder_id=? AND user_id=?', (id, uid))
    db.execute('DELETE FROM note_folders WHERE id=? AND user_id=?', (id, uid))
    db.commit()
    return jsonify({'ok': True})


@notes_bp.route('/notes/<int:id>/move', methods=['POST'])
@login_required
def move_note_to_folder(id):
    from app import get_db
    db = get_db()
    data = request.get_json()
    folder_id = data.get('folder_id')
    folder_id = int(folder_id) if folder_id else None
    db.execute('UPDATE notes SET folder_id=? WHERE id=? AND user_id=?', (folder_id, id, session['user_id']))
    db.commit()
    return jsonify({'ok': True})


# ─── API ──────────────────────────────────────────────────────────────────

@notes_bp.route('/api/notes/recent')
@login_required
def recent_notes():
    from app import get_db
    db = get_db()
    limit = request.args.get('limit', 5, type=int)
    notes = db.execute('SELECT id, title, updated_at FROM notes WHERE user_id=? ORDER BY updated_at DESC LIMIT ?',
                       (session['user_id'], limit)).fetchall()
    return jsonify([dict(n) for n in notes])


@notes_bp.route('/api/notes/quick-capture', methods=['POST'])
@login_required
def quick_capture():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': '内容不能为空'}), 400
    first_line = content.split('\n')[0].strip()
    title = first_line.lstrip('#').strip()[:30] or '快速记录'
    cursor = db.execute(
        'INSERT INTO notes (title, content, markdown, user_id) VALUES (?,?,?,?)',
        (title, content, content, uid)
    )
    db.commit()
    note_id = cursor.lastrowid
    sync_note_blocks(note_id, content, uid)
    note = db.execute(
        'SELECT n.*, c.name as course_name, c.color as course_color FROM notes n LEFT JOIN courses c ON n.course_id = c.id WHERE n.id=?',
        (note_id,)
    ).fetchone()
    return jsonify({
        'ok': True, 'note': dict(note),
        'blocks_count': len(parse_blocks_from_markdown(content, note_id, uid)) if content else 0
    })


@notes_bp.route('/api/notes/<int:id>', methods=['GET'])
@login_required
def api_get_note(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    note = db.execute(
        'SELECT n.*, c.name as course_name, c.color as course_color FROM notes n LEFT JOIN courses c ON n.course_id = c.id WHERE n.id=? AND n.user_id=?',
        (id, uid)
    ).fetchone()
    if not note:
        return jsonify({'error': 'not found'}), 404
    blocks = db.execute('SELECT * FROM note_blocks WHERE note_id=? ORDER BY sort_order', (id,)).fetchall()
    tags = db.execute('SELECT * FROM note_tags WHERE note_id=?', (id,)).fetchall()
    backlinks = get_backlinks(id, uid)
    return jsonify({
        'note': dict(note), 'md_content': note['markdown'] or note['content'] or '',
        'blocks': [dict(b) for b in blocks], 'tags': [dict(t) for t in tags],
        'backlinks': [dict(bl) for bl in backlinks]
    })


@notes_bp.route('/api/notes/<int:id>/update', methods=['POST'])
@login_required
def api_update_note(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    data = request.get_json()
    title = data.get('title', '').strip()
    markdown = data.get('markdown', '')
    if not title:
        return jsonify({'error': '标题不能为空'}), 400
    db.execute(
        'UPDATE notes SET title=?, content=?, markdown=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?',
        (title, markdown, markdown, id, uid)
    )
    db.commit()
    blocks = sync_note_blocks(id, markdown, uid)
    return jsonify({'ok': True, 'blocks_count': len(blocks)})


@notes_bp.route('/api/notes/search')
@login_required
def api_notes_search():
    from app import get_db
    db = get_db()
    uid = session['user_id']
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    like = f'%{q}%'
    results = db.execute('SELECT id, title FROM notes WHERE user_id=? AND title LIKE ? ORDER BY updated_at DESC LIMIT 10',
                         (uid, like)).fetchall()
    return jsonify([{'id': r['id'], 'title': r['title']} for r in results])


# ─── Note Detail ──────────────────────────────────────────────────────────

@notes_bp.route('/notes/<int:id>')
@login_required
def note_detail(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    note = db.execute(
        'SELECT n.*, c.name as course_name, c.color as course_color FROM notes n LEFT JOIN courses c ON n.course_id = c.id WHERE n.id=? AND n.user_id=?',
        (id, uid)
    ).fetchone()
    if not note:
        flash('笔记不存在', 'error')
        return redirect(url_for('notes.notes'))
    md_content = note['markdown'] or note['content'] or ''
    if not note['markdown'] and note['content']:
        db.execute('UPDATE notes SET markdown=? WHERE id=?', (note['content'], id))
        db.commit()
        md_content = note['content']
    blocks = db.execute('SELECT * FROM note_blocks WHERE note_id=? ORDER BY sort_order', (id,)).fetchall()
    if not blocks and md_content:
        sync_note_blocks(id, md_content, uid)
        blocks = db.execute('SELECT * FROM note_blocks WHERE note_id=? ORDER BY sort_order', (id,)).fetchall()
    tags = db.execute('SELECT * FROM note_tags WHERE note_id=?', (id,)).fetchall()
    backlinks = get_backlinks(id, uid)
    courses = db.execute('SELECT * FROM courses WHERE user_id=?', (uid,)).fetchall()
    folders = db.execute('SELECT id, name, parent_id FROM note_folders WHERE user_id=? ORDER BY name', (uid,)).fetchall()
    return render_template('note_detail.html',
        note=note, blocks=blocks, tags=tags, backlinks=backlinks, courses=courses, md_content=md_content, folders=folders
    )


@notes_bp.route('/notes/<int:id>/save', methods=['POST'])
@login_required
def save_note(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    note = db.execute('SELECT id FROM notes WHERE id=? AND user_id=?', (id, uid)).fetchone()
    if not note:
        return jsonify({'error': '笔记不存在'}), 404
    data = request.get_json()
    title = data.get('title', '').strip()
    markdown = data.get('markdown', '')
    course_id = data.get('course_id')
    folder_id = data.get('folder_id')
    if not title:
        return jsonify({'error': '标题不能为空'}), 400
    db.execute(
        'UPDATE notes SET title=?, content=?, markdown=?, course_id=?, folder_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        (title, markdown, markdown, course_id, folder_id, id)
    )
    db.commit()
    blocks = sync_note_blocks(id, markdown, uid)
    return jsonify({'ok': True, 'blocks_count': len(blocks), 'message': '已保存'})


@notes_bp.route('/notes/<int:id>/tags', methods=['POST'])
@login_required
def update_note_tags(id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    data = request.get_json()
    tags = data.get('tags', [])
    db.execute('DELETE FROM note_tags WHERE note_id=?', (id,))
    for tag in tags:
        name = tag.get('name', '').strip()
        value = tag.get('value', '').strip()
        if name:
            db.execute('INSERT INTO note_tags (note_id, tag_name, tag_value, user_id) VALUES (?,?,?,?)',
                       (id, name, value, uid))
    db.commit()
    return jsonify({'ok': True})


@notes_bp.route('/api/blocks/<block_id>/flashcard', methods=['POST'])
@login_required
def create_flashcard(block_id):
    from app import get_db
    db = get_db()
    uid = session['user_id']
    block = db.execute('SELECT * FROM note_blocks WHERE id=? AND user_id=?', (block_id, uid)).fetchone()
    if not block:
        return jsonify({'error': '块不存在'}), 404
    data = request.get_json()
    front = data.get('front', block['content'][:100])
    back = data.get('back', '')
    if not back:
        return jsonify({'error': '背面内容不能为空'}), 400
    today = date.today().isoformat()
    db.execute(
        'INSERT INTO flashcards (note_id, block_id, front, back, next_review, user_id) VALUES (?,?,?,?,?,?)',
        (block['note_id'], block_id, front, back, today, uid)
    )
    db.commit()
    return jsonify({'ok': True, 'message': '闪卡已创建'})
