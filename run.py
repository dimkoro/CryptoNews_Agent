import asyncio
import sys
import io
from datetime import datetime, timezone
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager

logger = setup_logger()

# ГЛОБАЛЬНЫЕ СЧЕТЧИКИ
CYCLE_START_TIME = datetime.now(timezone.utc)
CYCLE_PUBLISHED_COUNT = 0
CYCLE_ATTEMPTS_COUNT = 0
startup_event = asyncio.Event()

# НАСТРОЙКИ
SEARCH_WINDOW_HOURS = 4 

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
        dt_str = str(post['date_posted']).split('+')[0]
        post_date = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - post_date).total_seconds() / 3600
        if age_hours < 0: age_hours = 0
        raw_score = (views + (comments * 10)) / subs
        final_score = raw_score / (age_hours + 2)
        return final_score * 10000
    except Exception:
        return 0

async def scheduler(spy, db, ai, channels):
    global CYCLE_START_TIME, CYCLE_PUBLISHED_COUNT, CYCLE_ATTEMPTS_COUNT
    while True:
        logger.info(f'🔄 ЦИКЛ: Сбор новостей (4 часа)...')
        CYCLE_START_TIME = datetime.now(timezone.utc)
        CYCLE_PUBLISHED_COUNT = 0
        CYCLE_ATTEMPTS_COUNT = 0
        
        for ch in channels:
            await spy.harvest_channel(ch, db, hours=SEARCH_WINDOW_HOURS)
            await asyncio.sleep(2)
            
        candidates = await db.get_raw_candidates()
        if candidates:
            ranked = sorted(candidates, key=calculate_hype_score, reverse=True)
            logger.info(f'📊 Анализ {len(ranked)} новостей...')
            history = await db.get_recent_history(limit=25)
            for news in ranked:
                await asyncio.sleep(6)
                is_dupe = await ai.check_duplicate(news['text_1'], history)
                if is_dupe:
                    await db.set_status(news["id"], 'rejected')
                else:
                    await db.set_status(news["id"], 'queued')
                    history.append(news['text_1'])
                    logger.info(f'✅ ID {news["id"]} добавлен в очередь.')
        else:
            logger.info('💤 Свежих новостей нет.')

        logger.info('✅ Сбор завершен.')
        if not startup_event.is_set(): startup_event.set()
        await asyncio.sleep(4 * 3600)

async def main_loop():
    global CYCLE_PUBLISHED_COUNT, CYCLE_ATTEMPTS_COUNT
    try:
        logger.info('--- CRYPTONEWS AGENT v13.2 (STABLE STUDIO) ---')
        config = load_config()
        db = Database()
        await db.init_db()
        
        spy = TelegramSpy(config)
        await spy.start_spy()
        
        ai = AIService(config['gemini_key'], config['proxy'])
        img = ImageService(
            provider=config['image_provider'], 
            api_key=config['unsplash_key'],
            hf_key=config['hf_key'], 
            proxy=config['proxy']
        )
        
        bot_mgr = BotManager(config, db, spy.client, ai_service=ai, img_service=img)
        await bot_mgr.start()
        
        with open('channels.txt', 'r') as f:
            channels = [normalize_channel(l) for l in f if l.strip()]
            
        asyncio.create_task(scheduler(spy, db, ai, channels))
        
        logger.info('⏳ Жду данные...')
        await startup_event.wait()
        logger.info('🚀 МЕНЕДЖЕР АКТИВЕН.')
        
        log_timer = 0
        while True:
            if await db.is_busy():
                if log_timer % 12 == 0: logger.info('⏳ Жду решения админа...')
                log_timer += 1
                await asyncio.sleep(5)
                continue
            
            if CYCLE_PUBLISHED_COUNT >= 3:
                if log_timer % 360 == 0: logger.info(f'🎉 План выполнен ({CYCLE_PUBLISHED_COUNT}/3). Жду новый цикл...')
                log_timer += 1
                await asyncio.sleep(10)
                continue
                
            if CYCLE_ATTEMPTS_COUNT >= 5:
                if log_timer % 360 == 0: logger.info(f'🛑 Лимит попыток ({CYCLE_ATTEMPTS_COUNT}/5). Жду новый цикл...')
                log_timer += 1
                await asyncio.sleep(10)
                continue

            candidates = await db.get_queued_news()
            if candidates:
                target = candidates[0]
                logger.info(f'📢 В работе ID {target["id"]} (Pub: {CYCLE_PUBLISHED_COUNT}/3)')
                
                # 1. ТЕКСТЫ
                await asyncio.sleep(6)
                t1, t2 = await ai.generate_variants(target['text_1'])
                if not t1: 
                    await db.set_status(target['id'], 'rejected'); continue

                # 2. КАРТИНКИ
                logger.info('🎨 Рисуем ассеты...')
                await asyncio.sleep(4)
                prompt = await ai.generate_image_prompt(target['text_1'])
                
                # Gen 1 & 2
                i1 = None
                res = await img.get_image(prompt)
                if res: i1 = res.getvalue()
                
                i2 = None
                res = await img.get_image(prompt)
                if res: i2 = res.getvalue()
                
                # Orig 3
                i3 = None
                try:
                    m = await spy.client.get_messages(target['channel'], ids=target['msg_id'])
                    if m and m.media: 
                        i3 = await spy.client.download_media(m, file=bytes)
                        logger.info('📥 Оригинал скачан.')
                except: pass
                
                # Remake 4
                i4 = None
                if i3:
                    desc = await ai.describe_image_for_remake(i3)
                    if desc:
                        res = await img.get_image(desc)
                        if res: i4 = res.getvalue()
                
                await db.update_assets(target['id'], t1, t2, i1, i2, i3, i4)
                await bot_mgr.send_studio(await db.get_post(target['id']))
                
                CYCLE_ATTEMPTS_COUNT += 1
                logger.info(f'📨 Отправлено (Попытка {CYCLE_ATTEMPTS_COUNT}).')
                
                while True:
                    post_status = (await db.get_post(target['id']))['status']
                    if post_status == 'published':
                        CYCLE_PUBLISHED_COUNT += 1
                        logger.info(f'✅ ОПУБЛИКОВАНО! (Итого: {CYCLE_PUBLISHED_COUNT}/3)')
                        break
                    elif post_status == 'rejected':
                        logger.info('❌ ОТКЛОНЕНО. Ищу замену...')
                        break
                    await asyncio.sleep(2)
            else:
                if log_timer % 360 == 0: 
                    logger.info('💤 Очередь пуста. Жду планировщик...')
                log_timer += 1
                await asyncio.sleep(10)

    except Exception as e:
        logger.critical(f'Fatal Error: {e}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_loop())