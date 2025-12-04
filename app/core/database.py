import aiosqlite
import logging

logger = logging.getLogger('CryptoBot')
DB_NAME = 'crypto_agent.db'

class Database:
    def __init__(self):
        self.db_path = DB_NAME

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Полная пересборка для чистоты v13
            await db.execute('DROP TABLE IF EXISTS news_posts')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS news_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    msg_id INTEGER,
                    text_1 TEXT,
                    text_2 TEXT,
                    img_1 BLOB,
                    img_2 BLOB,
                    img_3 BLOB,
                    img_4 BLOB,
                    selected_txt INTEGER DEFAULT 1,
                    selected_img INTEGER DEFAULT 1,
                    preview_msg_id INTEGER,
                    control_msg_id INTEGER,
                    views INTEGER,
                    comments INTEGER,
                    subscribers INTEGER,
                    date_posted TIMESTAMP,
                    status TEXT DEFAULT 'raw',
                    last_query TEXT
                )
            ''')
            await db.commit()
            logger.info('📂 БД v13.2: Полная структура.')

    async def add_post(self, channel, msg_id, text, views, comments, subscribers, date_posted):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT id FROM news_posts WHERE channel = ? AND msg_id = ?', (channel, msg_id))
                if await cursor.fetchone(): return False
                await db.execute(
                    '''INSERT INTO news_posts 
                    (channel, msg_id, text_1, views, comments, subscribers, date_posted) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (channel, msg_id, text, views, comments, subscribers, date_posted)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f'DB Error: {e}')
            return False

    async def update_assets(self, post_id, t1, t2, i1, i2, i3, i4):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE news_posts 
                SET text_1=?, text_2=?, img_1=?, img_2=?, img_3=?, img_4=?, status='queued'
                WHERE id=?
            ''', (t1, t2, i1, i2, i3, i4, post_id))
            await db.commit()

    async def update_selection(self, post_id, type_sel, val):
        field = 'selected_txt' if type_sel == 'txt' else 'selected_img'
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE news_posts SET {field}=? WHERE id=?", (val, post_id))
            await db.commit()
            
    async def set_ids(self, post_id, preview_id, control_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE news_posts SET preview_msg_id=?, control_msg_id=? WHERE id=?", (preview_id, control_id, post_id))
            await db.commit()

    async def get_raw_candidates(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE status='raw'")
            return await cursor.fetchall()
            
    # ВОТ ЭТОТ МЕТОД БЫЛ ПОТЕРЯН - ВОЗВРАЩАЕМ ЕГО
    async def get_queued_news(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE status='queued' ORDER BY views DESC")
            return await cursor.fetchall()
            
    async def get_post(self, post_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM news_posts WHERE id=?", (post_id,))
            return await cursor.fetchone()
            
    async def set_status(self, post_id, status):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE news_posts SET status=? WHERE id=?", (status, post_id))
            await db.commit()
            
    async def is_busy(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT count(*) FROM news_posts WHERE status='moderation'")
            return (await cursor.fetchone())[0] > 0
            
    async def get_recent_history(self, limit=20):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT text_1 FROM news_posts WHERE status IN ('published', 'rejected') ORDER BY id DESC LIMIT ?", (limit,))
            return [row['text_1'] for row in await cursor.fetchall()]