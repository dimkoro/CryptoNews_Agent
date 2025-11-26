import aiosqlite
import logging

logger = logging.getLogger('CryptoBot')
DB_NAME = 'crypto_agent.db'

class Database:
    def __init__(self):
        self.db_path = DB_NAME

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
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
                    status TEXT DEFAULT 'raw' 
                )
            ''')
            # Сброс зависших статусов при перезапуске (если бот упал, возвращаем в очередь)
            await db.execute("UPDATE news_posts SET status='raw' WHERE status='moderation'")
            await db.commit()
            logger.info('📂 База данных: Очередь сброшена (moderation -> raw).')

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

    async def set_status(self, post_id, status):
        # Установка статуса: 'moderation', 'published', 'rejected'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE news_posts SET status=? WHERE id=?", (status, post_id))
            await db.commit()
            
    async def is_busy(self):
        # Проверяем, есть ли что-то, что сейчас висит на модерации
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT count(*) FROM news_posts WHERE status='moderation'")
            count = (await cursor.fetchone())[0]
            return count > 0