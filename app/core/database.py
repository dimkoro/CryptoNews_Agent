import aiosqlite
import logging

logger = logging.getLogger('CryptoBot')
DB_NAME = 'crypto_agent.db'

class Database:
    def __init__(self):
        self.db_path = DB_NAME

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица v4 (счетчики + статусы)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS news_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    msg_id INTEGER,
                    text TEXT,
                    views INTEGER,
                    comments INTEGER,
                    subscribers INTEGER,
                    date_posted TIMESTAMP,
                    status TEXT DEFAULT 'raw',
                    txt_attempts INTEGER DEFAULT 0,
                    img_attempts INTEGER DEFAULT 0,
                    last_query TEXT
                )
            ''')
            # Сброс зависших статусов при рестарте
            await db.execute("UPDATE news_posts SET status='queued' WHERE status='moderation'")
            await db.commit()
            logger.info('📂 База данных: Полная версия (All Methods).')

    async def add_post(self, channel, msg_id, text, views, comments, subscribers, date_posted):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT id FROM news_posts WHERE channel = ? AND msg_id = ?', (channel, msg_id))
                if await cursor.fetchone(): return False
                await db.execute(
                    'INSERT INTO news_posts (channel, msg_id, text, views, comments, subscribers, date_posted) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (channel, msg_id, text, views, comments, subscribers, date_posted)
                )
                await db.commit()
                return True
        except Exception: return False

    async def get_raw_candidates(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE status='raw'")
            return await cursor.fetchall()

    async def get_queued_news(self):
        # МЕТОД, КОТОРОГО НЕ ХВАТАЛО
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE status='queued' ORDER BY views DESC")
            return await cursor.fetchall()
            
    async def get_recent_history(self, limit=20):
        # ДЛЯ AI ПРОВЕРКИ ДУБЛЕЙ
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT text FROM news_posts WHERE status IN ('published', 'rejected') ORDER BY id DESC LIMIT ?", (limit,))
            return [row['text'] for row in await cursor.fetchall()]

    async def set_status(self, post_id, status):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE news_posts SET status=? WHERE id=?", (status, post_id))
            await db.commit()
            
    async def is_busy(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT count(*) FROM news_posts WHERE status='moderation'")
            return (await cursor.fetchone())[0] > 0
            
    async def get_post(self, post_id):
        # ДЛЯ КНОПОК
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE id=?", (post_id,))
            return await cursor.fetchone()
            
    async def increment_attempt(self, post_id, type_attempt, new_query=None):
        # ДЛЯ СЧЕТЧИКОВ
        async with aiosqlite.connect(self.db_path) as db:
            if type_attempt == 'txt':
                await db.execute("UPDATE news_posts SET txt_attempts = txt_attempts + 1 WHERE id=?", (post_id,))
            elif type_attempt == 'img':
                sql = "UPDATE news_posts SET img_attempts = img_attempts + 1"
                if new_query: sql += ", last_query=?"
                sql += " WHERE id=?"
                params = (new_query, post_id) if new_query else (post_id,)
                await db.execute(sql, params)
            await db.commit()