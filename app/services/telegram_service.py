from telethon import TelegramClient, functions
import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('CryptoBot')

class TelegramSpy:
    def __init__(self, config):
        self.config = config
        self.client = self._create_client()

    def _create_client(self):
        return TelegramClient(
            'anon_session', 
            self.config['api_id'], 
            self.config['api_hash'],
            connection_retries=None,     
            retry_delay=5,               
            auto_reconnect=True,         
            request_retries=5            
        )

    async def start_spy(self):
        logger.info('🕵️ Шпион: Подключение к Telegram...')
        await self.client.start()
        logger.info('🕵️ Шпион v17.3: В сети.')

    async def restart(self):
        logger.warning("🔄 Перезапуск клиента Telegram...")
        try:
            if self.client:
                await self.client.disconnect()
                await asyncio.sleep(1)
        except: pass
        self.client = self._create_client()
        await self.client.start()
        logger.info("✅ Клиент Telegram перезапущен.")

    async def harvest_channel(self, channel_username, db, hours=4):
        try:
            entity = await self.client.get_entity(channel_username)
            
            subs = 0
            try:
                if hasattr(entity, 'participants_count') and entity.participants_count:
                    subs = entity.participants_count
                else:
                    full = await self.client(functions.channels.GetFullChannelRequest(entity))
                    subs = full.full_chat.participants_count
            except:
                subs = 50000 

            logger.info(f'🔎 {channel_username}: Сканирую (Subs: {subs})...')
            
            count = 0
            errors = 0
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            async for msg in self.client.iter_messages(entity, limit=60):
                try:
                    if msg.date and msg.date < cutoff:
                        break

                    if not msg.message:
                        continue
                        
                    if len(msg.message) < 50:
                        continue
                    
                    dt = msg.date
                    views = msg.views if msg.views else 0
                    comments = 0
                    if msg.replies and getattr(msg.replies, 'replies', None):
                        comments = msg.replies.replies or 0
                    
                    await db.add_candidate(
                        channel=channel_username,
                        msg_id=msg.id,
                        text=msg.message,
                        views=views,
                        comments=comments,
                        date_posted=dt.isoformat(),
                        subs=subs 
                    )
                    count += 1
                except Exception as e:
                    if "UNIQUE" not in str(e).upper():
                        errors += 1
                        logger.error(f"Ошибка сохранения msg {msg.id}: {e}")
            
            logger.info(f'✅ {channel_username}: Найдено {count} постов (Ошибок: {errors})')
            
        except Exception as e:
            if "Wait" in str(e):
                logger.warning(f"⏳ FloodWait на канале {channel_username}. Пропускаем.")
            elif "Security" in str(e) or "Connection" in str(e):
                raise e 
            else:
                logger.error(f'❌ Ошибка доступа к {channel_username}: {e}')
