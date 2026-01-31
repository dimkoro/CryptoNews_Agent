import asyncio
import sys
import io
import os
import time
import ctypes
from datetime import datetime, timezone, timedelta
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager

VERSION = "v17.0 (Stable)"

logger = setup_logger()
SEARCH_WINDOW_HOURS = 4
MAX_QUEUE_AGE_HOURS = 6
cycle_ready = asyncio.Event()

def disable_quickedit():
    if sys.platform != 'win32': return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value &= ~0x0040
        kernel32.SetConsoleMode(handle, mode)
        logger.info("🛡 Windows QuickEdit Mode отключен.")
    except Exception as e:
        logger.warning(f"Не удалось отключить QuickEdit: {e}")

class CycleState:
    def __init__(self):
        self.published = 0
        self.attempts = 0
        self.start_time = datetime.now(timezone.utc)
        self.is_resumed = False
        self.active = False

STATE = CycleState()

def normalize_channel(line):
    line = line.strip()
    for prefix in ['https://', 'http://', 't.me/', '@']:
        line = line.replace(prefix, '')
    return line.rstrip('/')

def calculate_hype_score(post):
    try:
        views = post['views'] or 0
        comments = post['comments'] or 0
        subs = post['subscribers'] or 100000
        dt_val = post['date_posted']
        if isinstance(dt_val, str): 
            dt = datetime.fromisoformat(str(dt_val))
            if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
        else: dt = dt_val
        
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age < 0: age = 0
        score = ((views + comments * 10) / (subs if subs>0 else 100000)) / (age + 2)
        return score * 10000
    except: return 0

def cleanup_temp_files():
    try:
        now = time.time()
        deleted = 0
        folder = 'temp'
        if os.path.exists(folder):
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path):
                    if now - os.path.getmtime(path) > 86400:
                        try:
                            os.remove(path)
                            deleted += 1
                        except: pass
        if deleted > 0:
            logger.info(f"🧹 Уборщик: Удалено {deleted} старых файлов из temp.")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

async def scheduler(spy, db, ai, channels):
    while True:
        await db.cleanup_old_records(days=3)
        cleanup_temp_files()
        await ai.pick_best_model()
        
        logger.info(f'🔄 СБОРЩИК: Ищу новости за {SEARCH_WINDOW_HOURS}ч...')
        
        if not STATE.active:
            real_pub = await db.count_recent_published(hours=4)
            if real_pub > STATE.published:
                STATE.published = real_pub
                logger.info(f"♻️ Синхронизация: Реально опубликовано {STATE.published}/3")

        if not STATE.is_resumed:
            if (datetime.now(timezone.utc) - STATE.start_time).total_seconds() > 4 * 3600:
                 STATE.published = 0
                 STATE.attempts = 0
                 STATE.start_time = datetime.now(timezone.utc)
                 await db.save_state(STATE.start_time, 0, 0)
        else:
             STATE.is_resumed = False
        
        STATE.active = True
        cycle_ready.clear()
        
        for ch in channels:
            try:
                await spy.harvest_channel(ch, db, hours=SEARCH_WINDOW_HOURS)
            except Exception as e:
                if "Security error" in str(e) or "Connection" in str(e):
                    logger.error(f"🚨 КРИТИЧЕСКИЙ СБОЙ TELEGRAM: {e}. Перезапуск клиента...")
                    await spy.restart()
                    await asyncio.sleep(10)
                else:
                    logger.error(f"Ошибка сбора {ch}: {e}")
            await asyncio.sleep(2)
        
        candidates = await db.get_raw_candidates()
        fresh_candidates = []
        now = datetime.now(timezone.utc)
        
        for c in candidates:
            try:
                dt_val = c['date_posted']
                if isinstance(dt_val, str): 
                     dt = datetime.fromisoformat(str(dt_val))
                     if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
                else: dt = dt_val
                
                age_hours = (now - dt).total_seconds() / 3600
                
                if age_hours > SEARCH_WINDOW_HOURS:
                    await db.set_status(c['id'], 'expired')
                    continue
                fresh_candidates.append(c)
            except Exception as e:
                pass
            
        if fresh_candidates:
            ranked = sorted(fresh_candidates, key=calculate_hype_score, reverse=True)
            logger.info(f'📊 Анализ {len(ranked)} свежих новостей...')
            
            history = await db.get_recent_history(days=3)
            
            for news in ranked:
                await asyncio.sleep(7)
                try: 
                    is_dupe = await ai.check_duplicate(news['text_1'], history)
                except: is_dupe = False
                
                if is_dupe:
                    await db.set_status(news["id"], 'rejected')
                    logger.info(f'⏩ ID {news["id"]} - Дубликат (Пропуск).')
                else:
                    await db.set_status(news["id"], 'queued')
                    history.append(news['text_1'])
                    logger.info(f'✅ ID {news["id"]} прошел в очередь.')
        else:
            logger.info('💤 Свежих новостей нет.')

        logger.info('✅ Сбор завершен. Запускаю Цех.')
        cycle_ready.set()
        await asyncio.sleep(4 * 3600)

async def production(db, ai, img, spy, bot_mgr, config):
    logger.info('🏭 Цех готов.')
    was_busy_log = False
    
    while True:
        await cycle_ready.wait()
        
        STATE.published = await db.count_recent_published(hours=4)
        
        if STATE.published >= 3:
            if STATE.active: logger.info(f'🎉 ПЛАН ВЫПОЛНЕН ({STATE.published}/3). Жду цикл.'); STATE.active = False
            await asyncio.sleep(10); continue
        if STATE.attempts >= 5:
            if STATE.active: logger.info('🛑 ЛИМИТ ПОПЫТОК (5/5). Жду цикл.'); STATE.active = False
            await asyncio.sleep(10); continue

        if await db.is_busy():
            if not was_busy_log:
                logger.info("⏳ Цех: Жду решения модератора (тихий режим)...")
                was_busy_log = True
            await asyncio.sleep(5); continue
        else:
            was_busy_log = False
            
        candidates = await db.get_queued_news()
        if not candidates:
            if STATE.active: logger.info("💤 Цех: Очередь пуста. Жду поступлений."); STATE.active = False
            await asyncio.sleep(10); continue
            
        target = candidates[0]
        
        try:
            dt_val = target['date_posted']
            if isinstance(dt_val, str): 
                dt = datetime.fromisoformat(str(dt_val))
                if not dt.tzinfo: dt = dt.replace(tzinfo=timezone.utc)
            else: dt = dt_val
            
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age > MAX_QUEUE_AGE_HOURS:
                logger.warning(f"🗑 ID {target['id']} устарел в очереди ({age:.1f}ч). Skip.")
                await db.set_status(target['id'], 'expired')
                continue
        except Exception as e:
            logger.error(f"Age check err: {e}")

        logger.info(f'⚙️ В РАБОТЕ ID {target["id"]} (Try {STATE.attempts+1}/5)')
        
        t1, t2 = await ai.generate_variants(target['text_1'])
        if not t1: await db.set_status(target['id'], 'rejected'); continue
            
        logger.info('🎨 Рисуем (Формат 4:5)... (Пауза 30с)')
        prompt = await ai.generate_image_prompt(target['text_1'])
        
        i1_path = await img.get_image(prompt, style_type=config['style_1'])
        
        await asyncio.sleep(30)
        i2_path = await img.get_image(prompt, style_type=config['style_2'])
        
        if not i2_path: logger.warning("⚠️ Картинка 2 (Popart) не сгенерировалась.")
        
        i3 = None
        try:
            m = await spy.client.get_messages(target['channel'], ids=target['msg_id'])
            if m and m.media: 
                i3 = await spy.client.download_media(m, file=bytes)
                logger.info('📥 Оригинал скачан.')
        except Exception as e:
             logger.error(f"Ошибка загрузки медиа: {e}")
             if "WinError" in str(e) or "Security" in str(e):
                 await spy.restart()
        
        i4_path = None
        if i3:
            desc = await ai.describe_image_for_remake(i3)
            if desc and desc != "crypto art":
                await asyncio.sleep(7)
                i4_path = await img.get_image(desc, style_type=config['style_remake'])
            else:
                logger.warning("⚠️ Описание оригинала не удалось, ремейк пропущен.")
        
        if i3 and not i4_path:
             logger.warning("⚠️ Ремейк не сгенерировался (сбой Pollinations).")
            
        def read_file_safe(path):
            if path and os.path.exists(path):
                try:
                    with open(path, 'rb') as f: return f.read()
                except: return None
            return None
            
        await db.update_assets(
            target['id'], 
            t1, t2, 
            read_file_safe(i1_path), 
            read_file_safe(i2_path), 
            i3, 
            read_file_safe(i4_path if i3 else None)
        )
        
        await bot_mgr.send_studio(await db.get_post(target['id']))
        
        STATE.attempts += 1
        await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
        logger.info(f'📨 Отправлено в студию...')
        
        while True:
            s = (await db.get_post(target['id']))['status']
            if s == 'published': 
                STATE.published = await db.count_recent_published(hours=4)
                await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
                logger.info(f'✅ ОПУБЛИКОВАНО. ({STATE.published}/3)')
                break
            elif s == 'rejected':
                logger.info('❌ ОТКЛОНЕНО.')
                break
            await asyncio.sleep(2)

async def main_loop():
    disable_quickedit()
    logger.info(f'--- CRYPTONEWS AGENT {VERSION} ---')
    config = load_config()
    db = Database(); await db.init_db()
    spy = TelegramSpy(config); await spy.start_spy()
    ai = AIService(config['gemini_key'], config['proxy'])
    img = ImageService(provider=config['image_provider'], api_key=config['unsplash_key'], hf_key=config['hf_key'], proxy=config['proxy'])
    bot = BotManager(config, db, spy.client, ai, img); await bot.start()
    
    saved = await db.get_state()
    if saved:
        try:
            st = datetime.fromisoformat(saved['cycle_start_time'])
            if (datetime.now(timezone.utc) - st).total_seconds() < 4 * 3600:
                STATE.start_time = st
                STATE.attempts = saved['attempts_count']
                STATE.is_resumed = True
        except: pass
    
    def norm(l): return l.replace('https://', '').replace('t.me/', '').strip('/')
    try:
        with open('channels.txt', 'r') as f: ch = [norm(l.strip()) for l in f if l.strip()]
    except: ch = []
        
    asyncio.create_task(scheduler(spy, db, ai, ch))
    await production(db, ai, img, spy, bot, config)

if __name__ == '__main__':
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота пользователем.")
    except Exception as e:
        logger.critical(f"🔥 КРИТИЧЕСКАЯ ОШИБКА: {e}")