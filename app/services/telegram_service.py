from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from datetime import datetime, timedelta, timezone
import logging
import asyncio

logger = logging.getLogger('CryptoBot')

class TelegramSpy:
    def __init__(self, config):
        self.client = TelegramClient('anon_session', config['api_id'], config['api_hash'])
        self.phone = config['phone']
        self.subs_cache = {}

    async def start_spy(self):
        await self.client.start(phone=self.phone)
        logger.info('🕵️ Шпион в сети.')

    async def get_real_subs(self, entity):
        try:
            if entity.id in self.subs_cache: return self.subs_cache[entity.id]
            if hasattr(entity, 'participants_count') and entity.participants_count:
                return entity.participants_count
            full = await self.client(GetFullChannelRequest(entity))
            count = full.full_chat.participants_count
            self.subs_cache[entity.id] = count
            return count
        except: return 100000

    async def harvest_channel(self, channel_username, db, hours=4):
        try:
            entity = await self.client.get_entity(channel_username)
            subs_count = await self.get_real_subs(entity)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            count = 0
            async for msg in self.client.iter_messages(entity, limit=10):
                if msg.date < cutoff: break
                if msg.text and len(msg.text) > 50:
                    views = msg.views if msg.views else 0
                    comments = msg.replies.replies if (msg.replies and msg.replies.replies) else 0
                    if await db.add_post(channel_username, msg.id, msg.text, views, comments, subs_count, msg.date):
                        count += 1
            if count > 0: logger.info(f'✅ {channel_username}: +{count} (Subs: {subs_count})')
            else: logger.info(f'💤 {channel_username}: Пусто.')
        except Exception as e: logger.error(f'Skip {channel_username}: {e}')