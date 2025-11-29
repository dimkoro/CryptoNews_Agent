from telethon import TelegramClient, events, Button
import logging
import random
import asyncio
import io

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
        logger.info('🤖 Бот-Редактор запущен (v10.0 Final).')

    async def send_moderation(self, text, image_file, post_id):
        buttons = [
            [Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')],
            [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]
        ]
        try:
            if len(text) > 1000: text = text[:990] + "..."
            if image_file:
                await self.bot.send_message(self.mod_channel, text, file=image_file, buttons=buttons)
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
                
                await event.edit(f"⏳ <b>Генерирую текст (Попытка {attempts+1}/3)...</b>", parse_mode='html', buttons=None)
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
                
                # СЦЕНАРИЙ 4: ПУБЛИКАЦИЯ БЕЗ ФОТО
                if attempts >= 3:
                    await event.edit("🚫 <b>Лимит фото. Публикую текст...</b>", parse_mode='html', buttons=None)
                    await asyncio.sleep(2.0)
                    
                    raw_text = msg.text if msg.text else msg.caption
                    clean_text = raw_text.split('📊 Views')[0].strip() + '\n\n🚀 @CryptoNews'
                    
                    # Safe send
                    try:
                        await self.bot.send_message(self.pub_channel, clean_text)
                        await event.delete()
                        await self.db.set_status(post_id, 'published')
                    except Exception as e:
                        logger.error(f'Pub Error: {e}')
                        await event.answer('Ошибка публикации.', alert=True)
                    return

                # СЦЕНАРИЙ 3: ОРИГИНАЛ
                if attempts == 2:
                    await event.edit("📥 <b>Загружаю оригинал из источника...</b>", parse_mode='html', buttons=None)
                    await asyncio.sleep(1.0) # Пауза для UI
                    try:
                        source_msgs = await self.spy.get_messages(post['channel'], ids=post['msg_id'])
                        if source_msgs and source_msgs.media:
                            media_blob = await self.spy.download_media(source_msgs, file=bytes)
                            file_obj = io.BytesIO(media_blob)
                            file_obj.name = 'original.jpg'
                            
                            await event.delete()
                            buttons = [[Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')], [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]]
                            text_content = msg.text if msg.text else msg.caption
                            await self.bot.send_message(self.mod_channel, text_content, file=file_obj, buttons=buttons)
                            await self.db.increment_attempt(post_id, 'img', 'ORIGINAL_SOURCE')
                            return
                        else:
                            # Если нет фото - пропускаем ход, идем к текстовой публикации в след раз
                            await event.edit(msg.text, buttons=msg.buttons)
                            await event.answer('В оригинале нет фото! (След. клик - текст)', alert=True)
                            await self.db.increment_attempt(post_id, 'img', 'NO_SOURCE_IMG')
                            return
                    except Exception as e:
                        logger.error(f"Ошибка оригинала: {e}")
                        await event.edit(msg.text, buttons=msg.buttons)
                        await event.answer('Ошибка скачивания оригинала.', alert=True)
                        return

                # СЦЕНАРИЙ 1 и 2: ГЕНЕРАЦИЯ AI
                await event.edit("🖼 <b>Рисую новый арт...</b>", parse_mode='html', buttons=None)
                await asyncio.sleep(2.0) # Пауза для UI
                
                ai_prompt = await self.ai.generate_image_prompt(post['text'])
                img_file = await self.img.get_image(ai_prompt)
                
                if img_file:
                    await event.delete()
                    buttons = [[Button.inline('✅ Опубликовать', data=f'pub_{post_id}'), Button.inline('❌ Отклонить', data=f'del_{post_id}')], [Button.inline('📝 Текст', data=f'txt_{post_id}'), Button.inline('🖼 Картинка', data=f'img_{post_id}')]]
                    text_content = msg.text if msg.text else msg.caption
                    await self.bot.send_message(self.mod_channel, text_content, file=img_file, buttons=buttons)
                    await self.db.increment_attempt(post_id, 'img', ai_prompt)
                else:
                    await event.edit(msg.text, buttons=msg.buttons)
                    await event.answer('Ошибка генерации.', alert=True)
                
        except Exception as e:
            logger.error(f'Btn Err: {e}')