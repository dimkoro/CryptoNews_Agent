from telethon import TelegramClient, events, Button
import logging
import io

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

    async def start(self): await self.bot.start(bot_token=self.bot_token)

    async def send_studio(self, post):
        # 1. Альбом (Витрина)
        captions = ['1️⃣ Cyberpunk', '2️⃣ Art', '3️⃣ Оригинал', '4️⃣ Remake']
        a_ids = []
        for i, key in enumerate(['img_1', 'img_2', 'img_3', 'img_4']):
            if post[key]:
                f = io.BytesIO(post[key]); f.name=f'{i+1}.jpg'
                msg = await self.bot.send_message(self.mod, captions[i], file=f)
                a_ids.append(msg.id)
        self.album_map[post['id']] = a_ids
        
        # 2. Пульт + Превью (Запускаем интерфейс)
        await self.update_interface(post, is_new=True)

    async def update_interface(self, post, is_new=False, event=None):
        # --- ТЕКСТ ПУЛЬТА ---
        t1_s = (post['text_1'][:60] + '...') if post['text_1'] else '❌'
        t2_s = (post['text_2'][:60] + '...') if post['text_2'] else '❌'
        
        control_msg = (
            f"🎛 **ПУЛЬТ РЕДАКТОРА (ID {post['id']})**\n\n"
            f"1️⃣ _Hype:_ {t1_s}\n"
            f"2️⃣ _Strict:_ {t2_s}\n\n"
            f"👇 **ВЫБРАНО ДЛЯ ПРЕВЬЮ:**\n"
            f"Картинка: **#{post['selected_img']}** | Текст: **#{post['selected_txt']}**"
        )

        pid = post['id']
        si, st = post['selected_img'], post['selected_txt']
        
        # КНОПКИ ВЫБОРА
        control_btns = [
            [
                Button.inline(f"{'✅' if si==1 else ''} 1", f's_img_1_{pid}'),
                Button.inline(f"{'✅' if si==2 else ''} 2", f's_img_2_{pid}'),
                Button.inline(f"{'✅' if si==3 else ''} Orig", f's_img_3_{pid}'),
                Button.inline(f"{'✅' if si==4 else ''} Remake", f's_img_4_{pid}')
            ],
            [
                Button.inline(f"{'✅' if st==1 else ''} Текст 1", f's_txt_1_{pid}'),
                Button.inline(f"{'✅' if st==2 else ''} Текст 2", f's_txt_2_{pid}')
            ]
        ]
        
        # --- ПРЕВЬЮ (То, что пойдет в канал) ---
        final_txt = post[f'text_{st}']
        final_img = post[f'img_{si}']
        
        preview_caption = final_txt.strip() + f'\n\n👀 {post["views"]}\n🤖 #Draft'
        if len(preview_caption) > 1000: preview_caption = preview_caption[:990]+"..."
        
        # КНОПКИ ДЕЙСТВИЯ (Сразу под превью!)
        action_btns = [
            [Button.inline('🚀 В КАНАЛ', f'f_pub_{pid}')],
            [Button.inline('❌ В МУСОР', f'f_del_{pid}')],
            [Button.inline('📄 ТОЛЬКО ТЕКСТ', f'f_txt_{pid}')]
        ]

        if is_new:
            # Шлем пульт
            c_msg = await self.bot.send_message(self.mod, control_msg, buttons=control_btns, link_preview=False)
            
            # Шлем превью
            p_msg = None
            if final_img:
                f = io.BytesIO(final_img); f.name='p.jpg'
                p_msg = await self.bot.send_message(self.mod, preview_caption, file=f, buttons=action_btns, link_preview=False)
            else:
                p_msg = await self.bot.send_message(self.mod, preview_caption, buttons=action_btns, link_preview=False)
                
            await self.db.set_ids(pid, p_msg.id, c_msg.id)
            await self.db.set_status(pid, 'moderation')
            
        elif event:
            # Обновляем Пульт (галочки)
            try: await event.edit(control_msg, buttons=control_btns)
            except: pass
            
            # Обновляем Превью (удаляем старое -> шлем новое)
            # Это надежнее, чем edit_message для медиа
            if post['preview_msg_id']:
                try: await self.bot.delete_messages(self.mod, post['preview_msg_id'])
                except: pass
                
            p_msg = None
            if final_img:
                f = io.BytesIO(final_img); f.name='new.jpg'
                p_msg = await self.bot.send_message(self.mod, preview_caption, file=f, buttons=action_btns, link_preview=False)
            else:
                p_msg = await self.bot.send_message(self.mod, preview_caption, buttons=action_btns, link_preview=False)
            
            # Обновляем ID превью в базе (так как сообщение новое)
            # control_msg_id не меняется
            await self.db.set_ids(pid, p_msg.id, post['control_msg_id'])

    async def handler(self, event):
        try:
            d = event.data.decode('utf-8').split('_')
            act = d[0]
            
            if act == 's': # SELECT
                pid = int(d[3])
                type_sel = d[1] # img/txt
                val = int(d[2])
                
                # Проверка наличия
                post = await self.db.get_post(pid)
                if type_sel == 'img' and not post[f'img_{val}']:
                    await event.answer('Картинка недоступна', alert=True)
                    return
                
                await self.db.update_selection(pid, type_sel, val)
                post = await self.db.get_post(pid) # Reload
                await self.update_interface(post, event=event)
                await event.answer('Обновлено')
            
            elif act == 'f': # FINAL ACTION
                sub, pid = d[1], int(d[2])
                post = await self.db.get_post(pid)
                
                # Чистка интерфейса
                try:
                    if post['control_msg_id']: await self.bot.delete_messages(self.mod, post['control_msg_id'])
                    if post['preview_msg_id']: await self.bot.delete_messages(self.mod, post['preview_msg_id'])
                    if pid in self.album_map: await self.bot.delete_messages(self.mod, self.album_map[pid])
                except: pass
                
                if sub == 'del':
                    await self.db.set_status(pid, 'rejected')
                    await event.answer('Удалено')
                
                elif sub == 'pub' or sub == 'txt':
                    txt = post[f'text_{post["selected_txt"]}']
                    img = post[f'img_{post["selected_img"]}']
                    clean = txt.split('📊 Views')[0].strip() + '\n\n🚀 @CryptoNews'
                    
                    if sub == 'pub' and img:
                        f = io.BytesIO(img); f.name='post.jpg'
                        await self.bot.send_message(self.pub, clean, file=f)
                    else:
                        await self.bot.send_message(self.pub, clean)
                        
                    await self.db.set_status(pid, 'published')
                    await event.answer('Опубликовано!')
        except Exception as e: logger.error(f'Btn: {e}')