from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
import logging
import asyncio

logger = logging.getLogger('CryptoBot')

class TelegramSpy:
    def __init__(self, config):
        self.client = TelegramClient('anon_session', config['api_id'], config['api_hash'])
        self.phone = config['phone']

    async def start_spy(self):
        await self.client.start(phone=self.phone)
        logger.info('🕵️ Шпион в сети.')

    async def harvest_channel(self, channel_username, db, hours=4):
        try:
            entity = await self.client.get_entity(channel_username)
            
            # БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ПОДПИСЧИКОВ
            # Если атрибута нет, берем дефолтное значение
            subs_count = getattr(entity, 'participants_count', 100000)
            if not subs_count:
                subs_count = 100000
                
            cutoff_date = datetime.now(timezone.utc) - timedelta(hours=hours)
            count = 0
            
            async for msg in self.client.iter_messages(entity, limit=20):
                if msg.date < cutoff_date: break
                
                if msg.text and len(msg.text) > 50:
                    views = msg.views if msg.views else 0
                    comments = 0
                    if msg.replies and msg.replies.replies:
                        comments = msg.replies.replies
                        
                    saved = await db.add_post(
                        channel=channel_username,
                        msg_id=msg.id,
                        text=msg.text,
                        views=views,
                        comments=comments,
                        subscribers=subs_count,
                        date_posted=msg.date
                    )
                    if saved: count += 1
            
            if count > 0:
                logger.info(f'✅ {channel_username}: +{count} (Subs: {subs_count})')
            else:
                logger.info(f'💤 {channel_username}: Пусто.')
                
        except Exception as e:
            logger.error(f'Skip {channel_username}: {e}')