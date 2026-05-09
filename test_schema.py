import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'studyplanner.db')
db = sqlite3.connect(DB)

# Run the new schema
db.executescript('''
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
''')

# Add new columns to notes table if not exist
try:
    db.execute('ALTER TABLE notes ADD COLUMN markdown TEXT DEFAULT ""')
    print('Added notes.markdown column')
except Exception as e:
    print(f'notes.markdown: {e}')

try:
    db.execute('ALTER TABLE notes ADD COLUMN course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL')
    print('Added notes.course_id column')
except Exception as e:
    print(f'notes.course_id: {e}')

db.commit()

# Verify
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('Tables:', [t[0] for t in tables])

cols = db.execute('PRAGMA table_info(notes)').fetchall()
print('Notes columns:', [c[1] for c in cols])

for table in ['note_blocks', 'note_links', 'note_tags', 'flashcards']:
    cols = db.execute(f'PRAGMA table_info({table})').fetchall()
    print(f'{table}: {[c[1] for c in cols]}')

# Count existing notes
count = db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]
print(f'Existing notes: {count}')

db.close()
print('All schema checks passed!')
