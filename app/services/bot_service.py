from telethon import TelegramClient, events, Button
import logging

logger = logging.getLogger('CryptoBot')

class BotManager:
    def __init__(self, config, db, spy_client):
        self.bot = TelegramClient('bot_session', config['api_id'], config['api_hash'])
        self.bot_token = config['bot_token']
        self.db = db
        self.spy = spy_client
        self.mod_channel = int(config['mod_channel'])
        self.pub_channel = int(config['pub_channel'])
        self.bot.add_event_handler(self.button_handler, events.CallbackQuery)

    async def start(self):
        await self.bot.start(bot_token=self.bot_token)
        logger.info('🤖 Бот готов к командам.')

    async def send_moderation(self, text, image_url, post_id):
        # Кнопки
        buttons = [
            [Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')]
        ]
        try:
            # Сначала отправляем, потом меняем статус в БД
            if image_url:
                await self.bot.send_message(self.mod_channel, text, file=image_url, buttons=buttons)
            else:
                await self.bot.send_message(self.mod_channel, text, buttons=buttons)
            
            # ВАЖНО: Ставим статус 'moderation'. Теперь главный цикл будет ждать.
            await self.db.set_status(post_id, 'moderation')
            
        except Exception as e:
            logger.error(f'Ошибка отправки: {e}')

    async def button_handler(self, event):
        try:
            data = event.data.decode('utf-8')
            action, post_id = data.split('_')
            post_id = int(post_id)
            
            if action == 'del':
                await event.delete()
                # Только ТУТ меняем статус на final
                await self.db.set_status(post_id, 'rejected')
                await event.answer('Новость удалена.')
                logger.info(f'🗑 ID {post_id} отклонена. Жду следующую...')
                
            elif action == 'pub':
                msg = await event.get_message()
                clean_text = msg.text.split('📊 Views')[0].strip()
                clean_text += '\n\n🚀 @CryptoNews'
                
                if msg.media:
                    await self.bot.send_message(self.pub_channel, clean_text, file=msg.media)
                else:
                    await self.bot.send_message(self.pub_channel, clean_text)
                
                await event.delete()
                # И ТУТ меняем статус на final
                await self.db.set_status(post_id, 'published')
                await event.answer('✅ Опубликовано!')
                logger.info(f'✅ ID {post_id} опубликована. Жду следующую...')
                
        except Exception as e:
            logger.error(f'Ошибка кнопки: {e}')