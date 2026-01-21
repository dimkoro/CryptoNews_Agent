import asyncio
import sys
import io
from datetime import datetime, timezone, timedelta
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager

logger = setup_logger()
SEARCH_WINDOW_HOURS = 4
cycle_ready = asyncio.Event()

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
            dt_val = dt_val.split('+')[0]
            dt = datetime.fromisoformat(dt_val).replace(tzinfo=timezone.utc)
        else: dt = dt_val
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age < 0: age = 0
        score = ((views + comments * 10) / (subs if subs>0 else 100000)) / (age + 2)
        return score * 10000
    except: return 0

async def scheduler(spy, db, ai, channels):
    while True:
        logger.info(f'🔄 СБОРЩИК: Ищу новости за {SEARCH_WINDOW_HOURS}ч...')
        
        if not STATE.is_resumed:
            STATE.published = 0
            STATE.attempts = 0
            STATE.start_time = datetime.now(timezone.utc)
            await db.save_state(STATE.start_time, 0, 0)
        else:
             STATE.is_resumed = False
        
        STATE.active = True
        cycle_ready.clear()
        
        for ch in channels:
            await spy.harvest_channel(ch, db, hours=SEARCH_WINDOW_HOURS)
            await asyncio.sleep(2)
        
        candidates = await db.get_raw_candidates()
        fresh_candidates = []
        now = datetime.now(timezone.utc)
        for c in candidates:
            try:
                dt_val = c['date_posted']
                if isinstance(dt_val, str): 
                     dt_val = dt_val.split('+')[0]
                     dt = datetime.fromisoformat(dt_val).replace(tzinfo=timezone.utc)
                else: dt = dt_val
                if (now - dt).total_seconds() > SEARCH_WINDOW_HOURS * 3600:
                    await db.set_status(c['id'], 'expired')
                    continue
                fresh_candidates.append(c)
            except: pass
            
        if fresh_candidates:
            ranked = sorted(fresh_candidates, key=calculate_hype_score, reverse=True)
            logger.info(f'📊 Анализ {len(ranked)} свежих новостей...')
            history = await db.get_recent_history(limit=50)
            for news in ranked:
                # ИЗМЕНЕНИЕ: Увеличили задержку с 6 до 15 секунд
                await asyncio.sleep(15)
                try: is_dupe = await ai.check_duplicate(news['text_1'], history)
                except: is_dupe = False
                
                if is_dupe:
                    await db.set_status(news["id"], 'rejected')
                else:
                    await db.set_status(news["id"], 'queued')
                    history.append(news['text_1'])
                    logger.info(f'✅ ID {news["id"]} прошел в очередь.')
        else:
            logger.info('💤 Свежих новостей нет.')

        logger.info('✅ Сбор завершен. Запускаю Цех.')
        cycle_ready.set()
        await asyncio.sleep(4 * 3600)

async def production(db, ai, img, spy, bot_mgr):
    logger.info('🏭 Цех готов.')
    while True:
        await cycle_ready.wait()
        
        if STATE.published >= 3:
            if STATE.active: logger.info('🎉 ПЛАН ВЫПОЛНЕН (3/3). Жду цикл.'); STATE.active = False
            await asyncio.sleep(10); continue
        if STATE.attempts >= 5:
            if STATE.active: logger.info('🛑 ЛИМИТ ПОПЫТОК (5/5). Жду цикл.'); STATE.active = False
            await asyncio.sleep(10); continue

        if await db.is_busy():
            await asyncio.sleep(5); continue
            
        candidates = await db.get_queued_news()
        if not candidates:
            if STATE.active: logger.info('💤 Новостей нет.'); STATE.active = False
            await asyncio.sleep(10); continue
            
        target = candidates[0]
        logger.info(f'⚙️ В РАБОТЕ ID {target["id"]} (Try {STATE.attempts+1}/5)')
        
        t1, t2 = await ai.generate_variants(target['text_1'])
        if not t1: await db.set_status(target['id'], 'rejected'); continue
            
        logger.info('🎨 Рисуем... (Пауза 20с для защиты от лимитов)')
        prompt = await ai.generate_image_prompt(target['text_1'])
        
        i1_obj = await img.get_image(prompt)
        i1 = i1_obj.getvalue() if i1_obj else None
        
        await asyncio.sleep(20)
        
        i2_obj = await img.get_image(prompt)
        i2 = i2_obj.getvalue() if i2_obj else None
        
        i3 = None
        try:
            m = await spy.client.get_messages(target['channel'], ids=target['msg_id'])
            if m and m.media: 
                i3 = await spy.client.download_media(m, file=bytes)
                logger.info('📥 Оригинал скачан.')
        except: pass
        
        i4 = None
        if i3:
            desc = await ai.describe_image_for_remake(i3)
            if desc:
                await asyncio.sleep(20)
                i4_obj = await img.get_image(desc)
                if i4_obj: i4 = i4_obj.getvalue()
            
        await db.update_assets(target['id'], t1, t2, i1, i2, i3, i4)
        await bot_mgr.send_studio(await db.get_post(target['id']))
        
        STATE.attempts += 1
        await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
        logger.info(f'📨 Отправлено. Жду решения...')
        
        while True:
            s = (await db.get_post(target['id']))['status']
            if s == 'published': 
                STATE.published += 1
                await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
                logger.info(f'✅ ОПУБЛИКОВАНО. ({STATE.published}/3)')
                break
            elif s == 'rejected':
                logger.info('❌ ОТКЛОНЕНО.')
                break
            await asyncio.sleep(2)

async def main_loop():
    logger.info('--- CRYPTONEWS AGENT v15.4 (MODEL FIX) ---')
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
                STATE.published = saved['published_count']
                STATE.attempts = saved['attempts_count']
                STATE.is_resumed = True
                logger.info(f'♻️ ВОССТАНОВЛЕНО: Pub {STATE.published}/3')
        except: pass
    
    def norm(l): return l.replace('https://', '').replace('t.me/', '').strip('/')
    with open('channels.txt', 'r') as f: ch = [norm(l.strip()) for l in f if l.strip()]
        
    asyncio.create_task(scheduler(spy, db, ai, ch))
    await production(db, ai, img, spy, bot)

if __name__ == '__main__':
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_loop())
