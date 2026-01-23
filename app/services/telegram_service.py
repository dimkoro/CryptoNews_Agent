from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
import logging
from datetime import datetime, timezone

logger = logging.getLogger('CryptoBot')

class TelegramSpy:
    def __init__(self, config):
        self.client = TelegramClient('anon_session', config['api_id'], config['api_hash'])
        self.channels = []
        
    async def start_spy(self):
        await self.client.start()
        logger.info("🕵️ Шпион v15.9: В сети и готов к работе.")

    async def harvest_channel(self, channel_username, db, hours=4):
        try:
            entity = await self.client.get_entity(channel_username)
            posts = await self.client(GetHistoryRequest(
                peer=entity,
                limit=10,
                offset_date=None,
                offset_id=0,
                max_id=0,
                min_id=0,
                add_offset=0,
                hash=0
            ))
            
            count = 0
            for msg in posts.messages:
                if not msg.message: continue
                
                dt = msg.date
                if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                
                if age > hours: continue
                if await db.post_exists(channel_username, msg.id): continue
                
                # Собираем данные
                subs = 100000 # Заглушка, если API не отдает
                try:
                    full = await self.client.get_entity(channel_username)
                    if hasattr(full, 'participants_count') and full.participants_count:
                        subs = full.participants_count
                except: pass

                data = {
                    'channel': channel_username,
                    'msg_id': msg.id,
                    'date': dt.isoformat(),
                    'text': msg.message,
                    'views': msg.views if msg.views else 0,
                    'comments': 0,
                    'subs': subs
                }
                await db.save_post(data)
                count += 1
            
            if count > 0: logger.info(f"✅ {channel_username}: +{count} (Subs: {data['subs']})")
            else: logger.info(f"💤 {channel_username}: Пусто.")
                
        except Exception as e:
            # logger.warning(f"⚠️ Ошибка сбора {channel_username}: {e}")
            pass
