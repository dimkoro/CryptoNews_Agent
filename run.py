import asyncio
import sys
from datetime import datetime, timezone
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager

logger = setup_logger()

def calculate_hype_score(post):
    try:
        # ФОРМУЛА ПОПУЛЯРНОСТИ
        views = post['views'] or 0
        comments = post['comments'] or 0
        subs = post['subscribers'] or 100000
        
        post_date = datetime.fromisoformat(str(post['date_posted'])).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - post_date).total_seconds() / 3600
        if age_hours < 0: age_hours = 0
        
        # (Просмотры + Комменты*10) / Подписчики
        raw_score = (views + (comments * 10)) / subs
        # Штраф за старость
        final_score = raw_score / (age_hours + 2)
        return final_score * 10000
    except Exception:
        return 0

async def processing_cycle(spy, db, ai, channels):
    while True:
        logger.info('🔄 ЦИКЛ (4 часа): Старт сбора...')
        for ch in channels:
            await spy.harvest_channel(ch, db, hours=4)
            await asyncio.sleep(2)
            
        # ЛОГИКА ОТБОРА ЛУЧШЕГО
        candidates = await db.get_raw_candidates()
        if candidates:
            # 1. Сортируем: Самые хайповые ВВЕРХУ
            ranked = sorted(candidates, key=calculate_hype_score, reverse=True)
            logger.info(f'📊 Кандидатов: {len(ranked)}. Начинаем отбор (Король Горы)...')
            
            selected_count = 0
            history = await db.get_recent_history(limit=25)
            
            for news in ranked:
                if selected_count >= 3:
                    break
                
                # Так как мы идем от ТОП-1 вниз, если это дубль - значит более крутая версия
                # УЖЕ была обработана (в прошлом цикле или только что добавлена в history)
                is_dupe = await ai.check_duplicate(news['text'], history)
                
                if is_dupe:
                    # Если это дубль, то он слабее того, что уже в истории. В мусорку.
                    logger.info(f'❌ Отсев (Score {calculate_hype_score(news):.2f}): Дубль.')
                    await db.set_status(news["id"], 'rejected')
                else:
                    logger.info(f'✅ Принято (Score {calculate_hype_score(news):.2f}): Уникально.')
                    await db.set_status(news["id"], 'queued')
                    history.append(news['text']) # Добавляем в историю, чтобы отсечь слабые копии ниже
                    selected_count += 1
        else:
            logger.info('💤 Нет новостей.')
            
        logger.info('💤 Ждем 4 часа...')
        await asyncio.sleep(4 * 3600)

async def main_loop():
    try:
        logger.info('--- CRYPTONEWS AGENT 5.1 (SMART FILTER) ---')
        config = load_config()
        db = Database()
        await db.init_db()
        
        spy = TelegramSpy(config)
        await spy.start_spy()
        
        ai = AIService(config['gemini_key'], config['proxy'])
        img = ImageService(config['unsplash_key'], config['proxy'])
        
        bot_mgr = BotManager(config, db, spy.client, ai_service=ai, img_service=img)
        await bot_mgr.start()
        
        with open('channels.txt', 'r') as f:
            channels = [l.strip() for l in f if l.strip()]
        asyncio.create_task(processing_cycle(spy, db, ai, channels))
        
        logger.info('🚀 ГОТОВО. Очередь активна.')
        
        while True:
            # Проверка очереди на отправку
            if await db.is_busy():
                await asyncio.sleep(5)
                continue

            queued_news = await db.get_queued_news()
            if queued_news:
                target = queued_news[0]
                logger.info(f'📨 Обработка очереди: ID {target["id"]}')
                
                ai_response = await ai.rewrite_news(target['text'])
                if not ai_response: 
                    await db.set_status(target['id'], 'rejected')
                    continue

                if '|||' in ai_response:
                    text, query = ai_response.split('|||')
                else:
                    text, query = ai_response, 'crypto'
                    
                img_url = await img.get_image(query.strip())
                stats = f'📊 Views: {target["views"]}'
                caption = f'{text.strip()}\n\n{stats}\n🤖 #Draft'
                
                await bot_mgr.send_moderation(caption, img_url, target['id'])
                logger.info('📨 Жду кнопку...')
            
            await asyncio.sleep(10)
            
    except Exception as e:
        logger.critical(f'Fatal Error: {e}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_loop())