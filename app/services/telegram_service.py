from telethon import TelegramClient, functions
import logging
import os

logger = logging.getLogger('CryptoBot')

class TelegramSpy:
    def __init__(self, config):
        # Сессия сохранится в файл anon_session.session
        self.client = TelegramClient('anon_session', config['api_id'], config['api_hash'])
        self.phone = config['phone']
        self.config = config

    async def start_spy(self):
        logger.info('Попытка подключения к Telegram...')
        await self.client.start(phone=self.phone)
        me = await self.client.get_me()
        logger.info(f'Успешный вход как: {me.first_name} (@{me.username})')
        return True

    async def get_channel_info(self, channel_username):
        try:
            entity = await self.client.get_entity(channel_username)
            logger.info(f'Канал найден: {entity.title} (ID: {entity.id})')
            return entity
        except Exception as e:
            logger.error(f'Ошибка при поиске {channel_username}: {e}')
            return None