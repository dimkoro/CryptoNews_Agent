from telethon import TelegramClient, events, Button
import logging
import random
import asyncio

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
        logger.info('🤖 Бот-Редактор запущен (v7.3 UX Delay).')

    async def send_moderation(self, text, image_url, post_id):
        buttons = [
            [Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')],
            [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]
        ]
        try:
            if len(text) > 1000: text = text[:990] + "..."
            if image_url:
                await self.bot.send_message(self.mod_channel, text, file=image_url, buttons=buttons)
            else:
                await self.bot.send_message(self.mod_channel, text, buttons=buttons)
            await self.db.set_status(post_id, 'moderation')
        except Exception as e:
            logger.error(f'Err mod send: {e}')

    async def button_handler(self, event):
        try:
            msg = await event.get_message()
            data = event.data.decode('utf-8')
            action, post_id = data.split('_')
            post_id = int(post_id)
            post = await self.db.get_post(post_id)
            
            if not post:
                await event.answer('Ошибка: Новость не найдена.', alert=True)
                return

            logger.info(f'🔘 ACTION: [{action.upper()}] ID {post_id}')

            if action == 'del':
                await event.delete()
                await self.db.set_status(post_id, 'rejected')
                await event.answer('❌ Отклонено')
                
            elif action == 'pub':
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
                    await event.delete()
                    await self.db.set_status(post_id, 'rejected')
                    await event.answer('Лимит правок. Удалено.', alert=True)
                    return
                
                await event.edit(f"⏳ <b>Генерирую новый текст (Попытка {attempts+1}/3)...</b>", parse_mode='html', buttons=None)
                # Пауза 2 секунды для текста (он и так долго генерируется)
                await asyncio.sleep(2.0) 
                
                new_text_raw = await self.ai.rewrite_news(post['text'], instruction="Перепиши короче и живее.")
                if '|||' in new_text_raw: final_text, _ = new_text_raw.split('|||')
                else: final_text = new_text_raw
                
                stats = f'📊 Views: {post["views"]} (Edit #{attempts+1})'
                caption = f'{final_text.strip()}\n\n{stats}\n🤖 #Draft'
                if len(caption) > 1000: caption = caption[:990] + "..."
                
                buttons = [[Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')], [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]]
                await event.edit(caption, buttons=buttons)
                await self.db.increment_attempt(post_id, 'txt')
                
            elif action == 'img':
                attempts = post['img_attempts']
                if attempts >= 3:
                    await event.edit("🚫 <b>Лимит фото исчерпан. Публикую текст...</b>", parse_mode='html', buttons=None)
                    await asyncio.sleep(3.0)
                    clean_text = msg.text.split('📊 Views')[0].strip() + '\n\n🚀 @CryptoNews'
                    await self.bot.send_message(self.pub_channel, clean_text)
                    await event.delete()
                    await self.db.set_status(post_id, 'published')
                    return
                
                # UI: Показываем статус и ЖДЕМ 5 СЕКУНД
                await event.edit("🖼 <b>Ищу новое фото...</b>", parse_mode='html', buttons=None)
                await asyncio.sleep(5.0) 
                
                base = 'crypto ' + post['channel']
                suf = ['chart', 'tech', 'money', 'future', 'analysis']
                query = f"{base} {random.choice(suf)}"
                img_url = await self.img.get_image(query)
                
                if img_url:
                    await event.delete()
                    buttons = [[Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')], [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]]
                    text_content = msg.text if msg.text else msg.caption
                    await self.bot.send_message(self.mod_channel, text_content, file=img_url, buttons=buttons)
                    await self.db.increment_attempt(post_id, 'img', query)
                    logger.info(f'🖼 ID {post_id}: Фото обновлено.')
                else:
                    await event.edit(msg.text, buttons=msg.buttons)
                    await event.answer('Фото не найдено.', alert=True)
                
        except Exception as e:
            logger.error(f'Btn Err: {e}')