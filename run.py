import asyncio
import sys
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager

logger = setup_logger()

async def scheduler(spy, db, channels):
    while True:
        logger.info('⏰ Планировщик: Ищу свежие новости...')
        for ch in channels:
            await spy.harvest_channel(ch, db, hours=4)
            await asyncio.sleep(2)
        logger.info('💤 Сбор завершен. Пауза 4 часа...')
        await asyncio.sleep(4 * 3600)

async def main_loop():
    try:
        logger.info('--- ЗАПУСК (ОЧЕРЕДЬ МОДЕРАЦИИ) ---')
        config = load_config()
        db = Database()
        await db.init_db()
        
        spy = TelegramSpy(config)
        await spy.start_spy()
        
        ai = AIService(config['gemini_key'], config['proxy'])
        img = ImageService(config['unsplash_key'], config['proxy'])
        
        bot_mgr = BotManager(config, db, spy.client)
        await bot_mgr.start()
        
        with open('channels.txt', 'r') as f:
            channels = [l.strip() for l in f if l.strip()]
        asyncio.create_task(scheduler(spy, db, channels))
        
        logger.info('🚀 СИСТЕМА ГОТОВА. Жду действий админа...')
        
        while True:
            # 1. ПРОВЕРКА: Занят ли админ?
            is_busy = await db.is_busy()
            if is_busy:
                # Если есть новость со статусом 'moderation', мы ничего не делаем
                # logger.info('⏳ Жду решения по текущей новости...') # (можно раскомментировать для отладки)
                await asyncio.sleep(5)
                continue

            # 2. Если свободно — ищем кандидата
            candidates = await db.get_raw_candidates()
            if candidates:
                # Сортировка по просмотрам
                ranked = sorted(candidates, key=lambda x: x['views'] or 0, reverse=True)
                best_news = ranked[0] # Берем САМУЮ первую
                
                logger.info(f'📢 Взял в работу ID {best_news["id"]} (Views: {best_news["views"]})')
                
                ai_response = await ai.rewrite_news(best_news['text'])
                if not ai_response: 
                    # Если AI не справился, помечаем как ошибку, чтобы не застрять
                    await db.set_status(best_news['id'], 'rejected')
                    continue

                if '|||' in ai_response:
                    text, query = ai_response.split('|||')
                else:
                    text, query = ai_response, 'crypto'
                    
                img_url = await img.get_image(query.strip())
                stats = f'📊 Views: {best_news["views"]}'
                caption = f'{text.strip()}\n\n{stats}\n🤖 #Draft'
                
                # Отправляем в модерацию
                if len(caption) > 1000:
                     if img_url: await bot_mgr.bot.send_message(bot_mgr.mod_channel, file=img_url)
                     await bot_mgr.send_moderation(caption, None, best_news['id'])
                else:
                     await bot_mgr.send_moderation(caption, img_url, best_news['id'])
                
                logger.info('📨 Отправлено на модерацию. Жду нажатия кнопки...')
            
            await asyncio.sleep(10)
            
    except Exception as e:
        logger.critical(f'Fatal Error: {e}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_loop())