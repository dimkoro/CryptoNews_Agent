import aiosqlite
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('CryptoBot')

class Database:
    def __init__(self, db_path='crypto_agent.db'):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                msg_id INTEGER,
                date_posted TEXT,
                text_1 TEXT,
                text_2 TEXT,
                img_1 BLOB,
                img_2 BLOB,
                img_3 BLOB,
                img_4 BLOB,
                status TEXT DEFAULT 'new',
                views INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                subscribers INTEGER DEFAULT 0,
                preview_msg_id INTEGER,
                control_msg_id INTEGER,
                selected_img INTEGER DEFAULT 1,
                selected_txt INTEGER DEFAULT 1
            )''')
            await db.execute('''CREATE TABLE IF NOT EXISTS state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cycle_start_time TEXT,
                published_count INTEGER,
                attempts_count INTEGER
            )''')
            await db.commit()
            logger.info('📂 БД v16.3.1: Умная дедупликация готова.')

    async def cleanup_old_records(self, days=3):
        try:
            limit_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM posts WHERE date_posted < ?", (limit_date,))
                await db.commit()
        except Exception as e: logger.error(f"Cleanup error: {e}")

    async def get_recent_history(self, days=3):
        limit_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT text_1 FROM posts WHERE date_posted > ? AND status IN ('published', 'queued') ORDER BY id DESC", 
                (limit_date,)
            ) as cursor:
                return [row[0] for row in await cursor.fetchall() if row[0]]

    async def post_exists(self, channel, msg_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT id FROM posts WHERE channel = ? AND msg_id = ?', (channel, msg_id)) as cursor:
                return await cursor.fetchone() is not None

    async def save_post(self, data):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''INSERT INTO posts 
                (channel, msg_id, date_posted, text_1, views, comments, subscribers) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (data['channel'], data['msg_id'], data['date'], data['text'], data['views'], data['comments'], data['subs'])
            )
            await db.commit()

    async def get_raw_candidates(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM posts WHERE status = 'new'") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def set_status(self, pid, status):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE posts SET status = ? WHERE id = ?", (status, pid))
            await db.commit()

    async def get_queued_news(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM posts WHERE status = 'queued' ORDER BY id ASC LIMIT 1") as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def update_assets(self, pid, t1, t2, i1, i2, i3, i4):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''UPDATE posts SET 
                text_1=?, text_2=?, img_1=?, img_2=?, img_3=?, img_4=? 
                WHERE id=?''', (t1, t2, i1, i2, i3, i4, pid))
            await db.commit()

    async def get_post(self, pid):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM posts WHERE id = ?", (pid,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def set_ids(self, pid, p_id, c_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE posts SET preview_msg_id=?, control_msg_id=? WHERE id=?", (p_id, c_id, pid))
            await db.commit()

    async def update_selection(self, pid, type_sel, val):
        col = 'selected_img' if type_sel == 'img' else 'selected_txt'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE posts SET {col}=? WHERE id=?", (val, pid))
            await db.commit()

    async def is_busy(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM posts WHERE status = 'moderation'") as cursor:
                return await cursor.fetchone() is not None
    
    async def save_state(self, start_time, published, attempts):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO state (id, cycle_start_time, published_count, attempts_count) VALUES (1, ?, ?, ?)",
                (start_time.isoformat(), published, attempts))
            await db.commit()
            
    async def get_state(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM state WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
