from telethon import TelegramClient, events, Button
import logging
import random

logger = logging.getLogger('CryptoBot')

class BotManager:
    def __init__(self, config, db, spy_client, ai_service, img_service):
        self.bot = TelegramClient('bot_session', config['api_id'], config['api_hash'])
        self.bot_token = config['bot_token']
        self.db = db
        self.spy = spy_client
        self.ai = ai_service
        self.img = img_service
        self.mod_channel = int(config['mod_channel'])
        self.pub_channel = int(config['pub_channel'])
        self.bot.add_event_handler(self.button_handler, events.CallbackQuery)

    async def start(self):
        await self.bot.start(bot_token=self.bot_token)
        logger.info('🤖 Бот-Редактор запущен.')

    async def send_moderation(self, text, image_url, post_id):
        buttons = [
            [Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')],
            [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]
        ]
        try:
            if image_url:
                await self.bot.send_message(self.mod_channel, text, file=image_url, buttons=buttons)
            else:
                await self.bot.send_message(self.mod_channel, text, buttons=buttons)
            await self.db.set_status(post_id, 'moderation')
        except Exception as e:
            logger.error(f'Err mod send: {e}')

    async def button_handler(self, event):
        try:
            # ГЛАВНОЕ ИСПРАВЛЕНИЕ: Сначала получаем само сообщение надежным способом
            msg = await event.get_message()
            
            data = event.data.decode('utf-8')
            action, post_id = data.split('_')
            post_id = int(post_id)
            post = await self.db.get_post(post_id)
            
            if not post:
                await event.answer('Ошибка: Новость не найдена.', alert=True)
                return

            # --- ЛОГИКА ---
            
            if action == 'del':
                await event.delete()
                await self.db.set_status(post_id, 'rejected')
                await event.answer('❌ Отклонено.')
                
            elif action == 'pub':
                # Используем полученный msg вместо event.message
                clean_text = msg.text.split('📊 Views')[0].strip()
                clean_text += '\n\n🚀 @CryptoNews'
                
                if msg.media:
                    await self.bot.send_message(self.pub_channel, clean_text, file=msg.media)
                else:
                    await self.bot.send_message(self.pub_channel, clean_text)
                
                await event.delete()
                await self.db.set_status(post_id, 'published')
                await event.answer('✅ Опубликовано!')
                
            elif action == 'txt':
                attempts = post['txt_attempts']
                if attempts >= 3:
                    await event.answer('🚫 Лимит попыток исчерпан!', alert=True)
                    return
                
                await event.answer('📝 Переписываю...')
                new_text_raw = await self.ai.rewrite_news(post['text'], instruction="Перепиши текст другими словами.")
                
                if not new_text_raw:
                    await event.answer('Ошибка AI', alert=True)
                    return

                if '|||' in new_text_raw:
                    final_text, _ = new_text_raw.split('|||')
                else:
                    final_text = new_text_raw
                
                stats = f'📊 Views: {post["views"]} (Draft #{attempts+1})'
                caption = f'{final_text.strip()}\n\n{stats}\n🤖 #Draft'
                
                # Используем msg.buttons, чтобы сохранить кнопки
                await event.edit(caption, buttons=msg.buttons)
                await self.db.increment_attempt(post_id, 'txt')
                
            elif action == 'img':
                attempts = post['img_attempts']
                if attempts >= 3:
                    await event.delete()
                    clean_text = msg.text.split('📊 Views')[0].strip()
                    clean_text += '\n\n🚀 @CryptoNews'
                    await self.bot.send_message(self.pub_channel, clean_text)
                    await self.db.set_status(post_id, 'published')
                    await event.answer('🚫 Фото кончились. Опубликовано текстом.', alert=True)
                    return
                
                await event.answer('🖼 Ищу новое фото...')
                base_query = 'crypto ' + post['channel']
                suffixes = ['trading chart', 'digital money', 'blockchain technology', 'financial growth', 'bitcoin coin']
                new_query = f"{base_query} {random.choice(suffixes)}"
                
                img_url = await self.img.get_image(new_query)
                
                if img_url:
                    current_text = msg.text
                    await event.delete()
                    # Вручную восстанавливаем кнопки
                    buttons = [
                        [Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')],
                        [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]
                    ]
                    await self.bot.send_message(self.mod_channel, current_text, file=img_url, buttons=buttons)
                    await self.db.increment_attempt(post_id, 'img', new_query)
                else:
                    await event.answer('Не нашел фото :(', alert=True)
                
        except Exception as e:
            logger.error(f'Button Error: {e}')