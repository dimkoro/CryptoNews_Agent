from telethon import TelegramClient, events, Button
import logging
import io
import asyncio
import re
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger('CryptoBot')

class BotManager:
    def __init__(self, config, db, spy_client, ai_service, img_service):
        self.bot = TelegramClient('bot_session', config['api_id'], config['api_hash'])
        self.bot_token = config['bot_token']
        self.db = db
        self.spy = spy_client
        self.pub = int(config['pub_channel'])
        self.mod = int(config['mod_channel'])
        self.bot.add_event_handler(self.handler, events.CallbackQuery)
        self.album_map = {}
        self.s1_name = config['style_1'].capitalize()
        self.s2_name = config['style_2'].capitalize()
        self.sr_name = config['style_remake'].capitalize()
        self.sig_txt = config['channel_signature']
        self.sig_url = config['channel_url']

    async def start(self): await self.bot.start(bot_token=self.bot_token)

    def _get_image_bytes(self, post, idx):
        path_key = f'img_{idx}_path'
        blob_key = f'img_{idx}'
        path = post.get(path_key)
        if path and os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    return f.read()
            except Exception:
                pass
        return post.get(blob_key)

    async def send_studio(self, post):
        captions = [f'1️⃣ {self.s1_name}', f'2️⃣ {self.s2_name}', '3️⃣ Оригинал', f'4️⃣ Remake ({self.sr_name})']
        a_ids = []
        for i in range(4):
            img_bytes = self._get_image_bytes(post, i + 1)
            if img_bytes:
                try:
                    f = io.BytesIO(img_bytes); f.name=f'{i+1}.jpg'
                    msg = await self.bot.send_message(self.mod, captions[i], file=f)
                    a_ids.append(msg.id)
                except Exception as e: logger.error(f"Album send err: {e}")
        self.album_map[post['id']] = a_ids
        await self.update_interface(post, is_new=True)

    async def update_interface(self, post, is_new=False, event=None):
        try:
            dt_val = post['date_posted']
            if isinstance(dt_val, str):
                dt = datetime.fromisoformat(str(dt_val))
            else: dt = dt_val
            
            if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
            msk_tz = timezone(timedelta(hours=3))
            dt_msk = dt.astimezone(msk_tz)
            time_str = dt_msk.strftime("%d.%m %H:%M")
        except: 
            time_str = "??:??"

        t1_s = (post['text_1'][:40] + '...') if post['text_1'] else '❌'
        t2_s = (post['text_2'][:40] + '...') if post['text_2'] else '❌'
        
        control_msg = (
            f"🎛 **ПУЛЬТ (ID {post['id']} | 🕒 {time_str} МСК)**\n\n"
            f"1️⃣ _Hype:_ {t1_s}\n"
            f"2️⃣ _RBC:_ {t2_s}\n\n"
            f"👇 **ВЫБРАНО ДЛЯ ПРЕВЬЮ:**\n"
            f"Картинка: **#{post['selected_img']}** | Текст: **#{post['selected_txt']}**"
        )

        pid = post['id']
        si, st = post['selected_img'], post['selected_txt']
        
        control_btns = [
            [
                Button.inline(f"{'✅' if si==1 else ''} {self.s1_name}", f's_img_1_{pid}'),
                Button.inline(f"{'✅' if si==2 else ''} {self.s2_name}", f's_img_2_{pid}'),
                Button.inline(f"{'✅' if si==3 else ''} Orig", f's_img_3_{pid}'),
                Button.inline(f"{'✅' if si==4 else ''} Remake", f's_img_4_{pid}')
            ],
            [
                Button.inline(f"{'✅' if st==1 else ''} Hype", f's_txt_1_{pid}'),
                Button.inline(f"{'✅' if st==2 else ''} RBC", f's_txt_2_{pid}')
            ]
        ]
        
        final_txt = post[f'text_{st}']
        final_img = self._get_image_bytes(post, si)
        
        footer = f'\n\n🤖 #Draft'
        max_body_len = 1024 - len(footer) - 50
        
        body_txt = final_txt.strip()
        if len(body_txt) > max_body_len:
             body_txt = body_txt[:max_body_len] + "..."
             
        preview_caption = body_txt + footer
        
        action_btns = [
            [Button.inline('🚀 В КАНАЛ', f'f_pub_{pid}')],
            [Button.inline('❌ В МУСОР', f'f_del_{pid}')],
            [Button.inline('📄 ТОЛЬКО ТЕКСТ', f'f_txt_{pid}')]
        ]

        if is_new:
            c_msg = await self.bot.send_message(self.mod, control_msg, buttons=control_btns, link_preview=False)
            p_msg = None
            if final_img:
                f = io.BytesIO(final_img); f.name='p.jpg'
                p_msg = await self.bot.send_message(self.mod, preview_caption, file=f, buttons=action_btns, link_preview=False)
            else:
                p_msg = await self.bot.send_message(self.mod, preview_caption, buttons=action_btns, link_preview=False)
                
            await self.db.set_ids(pid, p_msg.id, c_msg.id)
            await self.db.set_status(pid, 'moderation')
            
        elif event:
            try: await event.edit(control_msg, buttons=control_btns)
            except: pass
            
            if post['preview_msg_id']:
                try: await self.bot.delete_messages(self.mod, post['preview_msg_id'])
                except: pass
                
            p_msg = None
            if final_img:
                f = io.BytesIO(final_img); f.name='new.jpg'
                p_msg = await self.bot.send_message(self.mod, preview_caption, file=f, buttons=action_btns, link_preview=False)
            else:
                p_msg = await self.bot.send_message(self.mod, preview_caption, buttons=action_btns, link_preview=False)
            
            await self.db.set_ids(pid, p_msg.id, post['control_msg_id'])

    async def handler(self, event):
        try:
            d = event.data.decode('utf-8').split('_')
            act = d[0]
            
            if act == 's':
                pid = int(d[3])
                type_sel = d[1]
                val = int(d[2])
                post = await self.db.get_post(pid)
                if type_sel == 'img' and not self._get_image_bytes(post, val):
                    await event.answer('Картинка недоступна', alert=True)
                    return
                await self.db.update_selection(pid, type_sel, val)
                post = await self.db.get_post(pid)
                await self.update_interface(post, event=event)
                await event.answer('Обновлено')
            
            elif act == 'f':
                sub, pid = d[1], int(d[2])
                post = await self.db.get_post(pid)
                
                try:
                    if sub == 'del':
                        await self.db.set_status(pid, 'rejected')
                        await event.answer('Удалено')
                    
                    elif sub == 'pub' or sub == 'txt':
                        final_txt = post[f'text_{post["selected_txt"]}']
                        # LIVE EDIT FETCH
                        try:
                            msgs = await self.bot.get_messages(self.mod, ids=[event.message_id])
                            if msgs and msgs[0] and msgs[0].text:
                                raw = msgs[0].text
                                clean = re.sub(r'(\s*\n\s*)?(🤖|👀).*$', '', raw, flags=re.DOTALL)
                                final_txt = clean.strip()
                        except Exception as e: logger.error(f"Fetch Error: {e}")

                        img = self._get_image_bytes(post, post["selected_img"])
                        
                        # DYNAMIC SIGNATURE
                        footer_link = self.sig_txt
                        if self.sig_url:
                            footer_link = f"[{self.sig_txt}]({self.sig_url})"
                        content = final_txt + f'\n\n🚀 {footer_link}'
                        
                        if sub == 'pub' and img:
                            f = io.BytesIO(img); f.name='post.jpg'
                            await self.bot.send_message(self.pub, content, file=f)
                        else:
                            await self.bot.send_message(self.pub, content)
                            
                        await self.db.set_status(pid, 'published')
                        await event.answer('Опубликовано!')
                        
                finally:
                    # Точечная очистка (БЕЗ AUTO-PURGE)
                    to_delete = []
                    if post['control_msg_id']: to_delete.append(post['control_msg_id'])
                    if post['preview_msg_id']: to_delete.append(post['preview_msg_id'])
                    if pid in self.album_map: to_delete.extend(self.album_map[pid])
                    
                    if to_delete:
                        try: 
                            await self.bot.delete_messages(self.mod, to_delete)
                            logger.info(f"🗑 Удалены сообщения: {to_delete}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка удаления: {e}")
                        
        except Exception as e: logger.error(f'Btn: {e}')
