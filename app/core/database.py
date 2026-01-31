import aiosqlite
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger('CryptoBot')

class Database:
    def __init__(self, db_path='bot_database.db'):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                msg_id INTEGER,
                text_1 TEXT,
                text_2 TEXT,
                img_1 BLOB,
                img_2 BLOB,
                img_3 BLOB,
                img_4 BLOB,
                status TEXT DEFAULT 'new',
                date_posted TEXT,
                views INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                subscribers INTEGER DEFAULT 0,
                control_msg_id INTEGER,
                preview_msg_id INTEGER,
                selected_img INTEGER DEFAULT 1,
                selected_txt INTEGER DEFAULT 1,
                UNIQUE(channel, msg_id)
            )''')
            
            await db.execute('''CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
            await db.commit()
        logger.info(f'📂 БД v17.0: Все системы в норме.')

    async def add_candidate(self, channel, msg_id, text, views, comments, date_posted, subs):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''INSERT OR IGNORE INTO candidates 
                    (channel, msg_id, text_1, views, comments, date_posted, subscribers) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (channel, msg_id, text, views, comments, date_posted, subs))
                await db.commit()
            except Exception as e:
                logger.error(f"DB Error add_candidate: {e}")

    async def get_raw_candidates(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM candidates WHERE status = 'new'")
            return [dict(row) for row in await cursor.fetchall()]

    async def get_queued_news(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM candidates WHERE status = 'queued' ORDER BY id ASC LIMIT 1")
            return [dict(row) for row in await cursor.fetchall()]

    async def get_post(self, pid):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM candidates WHERE id = ?", (pid,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_assets(self, pid, t1, t2, i1, i2, i3, i4):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''UPDATE candidates SET 
                text_1 = ?, text_2 = ?, 
                img_1 = ?, img_2 = ?, img_3 = ?, img_4 = ? 
                WHERE id = ?''', (t1, t2, i1, i2, i3, i4, pid))
            await db.commit()

    async def set_status(self, pid, status):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE candidates SET status = ? WHERE id = ?", (status, pid))
            await db.commit()
            
    async def set_ids(self, pid, preview_id, control_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE candidates SET preview_msg_id = ?, control_msg_id = ? WHERE id = ?", 
                           (preview_id, control_id, pid))
            await db.commit()

    async def update_selection(self, pid, type_sel, val):
        field = 'selected_img' if type_sel == 'img' else 'selected_txt'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE candidates SET {field} = ? WHERE id = ?", (val, pid))
            await db.commit()

    async def cleanup_old_records(self, days=3):
        async with aiosqlite.connect(self.db_path) as db:
            pass

    async def get_recent_history(self, days=3):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT text_1 FROM candidates WHERE status IN ('published', 'queued') ORDER BY id DESC LIMIT 50")
            rows = await cursor.fetchall()
            return [r[0] for r in rows if r[0]]

    async def save_state(self, start_time, pub_count, attempts):
        async with aiosqlite.connect(self.db_path) as db:
            val = json.dumps({
                'cycle_start_time': start_time.isoformat(),
                'published_count': pub_count,
                'attempts_count': attempts
            })
            await db.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('cycle', ?)", (val,))
            await db.commit()
            
    async def get_state(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM state WHERE key = 'cycle'")
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
            
    async def count_recent_published(self, hours=4):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT count(*) FROM candidates WHERE status = 'published'")
            row = await cursor.fetchone()
            return row[0] if row else 0
            
    async def is_busy(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT count(*) FROM candidates WHERE status = 'moderation'")
            row = await cursor.fetchone()
            return row[0] > 0