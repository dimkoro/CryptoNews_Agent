import aiosqlite
import logging

logger = logging.getLogger('CryptoBot')
DB_NAME = 'crypto_agent.db'

class Database:
    def __init__(self):
        self.db_path = DB_NAME

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Удаляем старую таблицу для обновления структуры
            await db.execute('DROP TABLE IF EXISTS news_posts')
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
            await db.commit()
            logger.info('📂 База данных: Структура обновлена (v3: Smart Rank).')

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
        except Exception as e:
            logger.error(f'Ошибка БД: {e}')
            return False

    async def get_raw_candidates(self):
        # Получаем все необработанные новости для анализа в Python
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE status='raw'")
            return await cursor.fetchall()
            
    async def mark_as_published(self, post_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE news_posts SET status='published' WHERE id=?", (post_id,))
            await db.commit()