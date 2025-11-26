import asyncio
import sys
from datetime import datetime, timezone
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService

logger = setup_logger()

def calculate_hype_score(post):
    try:
        views = post['views'] or 0
        comments = post['comments'] or 0
        subs = post['subscribers'] or 100000
        post_date = datetime.fromisoformat(str(post['date_posted'])).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - post_date).total_seconds() / 3600
        if age_hours < 0: age_hours = 0
        raw_score = (views + (comments * 10)) / subs
        final_score = raw_score / (age_hours + 2)
        return final_score * 10000
    except Exception:
        return 0

async def main():
    try:
        logger.info('--- ЗАПУСК УМНОГО АНАЛИЗАТОРА (v2: Safe Mode) ---')
        config = load_config()
        db = Database()
        await db.init_db()
        
        spy = TelegramSpy(config)
        ai = AIService(config['gemini_key'], config['proxy'])
        img = ImageService(config['unsplash_key'], config['proxy'])
        
        await spy.start_spy()
        
        # 1. СБОР
        logger.info('🚜 Сбор данных...')
        with open('channels.txt', 'r') as f:
            channels = [l.strip() for l in f if l.strip()]
        for ch in channels:
            await spy.harvest_channel(ch, db, hours=4)
            await asyncio.sleep(2)
            
        # 2. УМНЫЙ ОТБОР
        candidates = await db.get_raw_candidates()
        if not candidates:
            logger.info('Нет новостей.')
            return
            
        ranked_news = sorted(candidates, key=calculate_hype_score, reverse=True)
        top_3 = ranked_news[:3]
        
        logger.info(f'🏆 Проанализировано {len(candidates)} новостей. Отобрано Топ-3.')
        
        # 3. ПУБЛИКАЦИЯ
        mod_channel = int(config['mod_channel'])
        for news in top_3:
            score = calculate_hype_score(news)
            logger.info(f'Processing: {news["channel"]} (Score: {score:.2f})')
            
            ai_response = await ai.rewrite_news(news['text'])
            if not ai_response: continue
            
            if '|||' in ai_response:
                text, query = ai_response.split('|||')
            else:
                text, query = ai_response, 'crypto chart'
                
            img_url = await img.get_image(query.strip())
            
            stats = f'📊 HypeScore: {score:.1f} | 👀 {news["views"]} | 💬 {news["comments"]}'
            caption = f'{text.strip()}\n\n{stats}\n🤖 #SmartCryptoAgent'
            
            try:
                # ЛОГИКА "SPLIT & SAFE"
                # Если текст слишком длинный (>1000) или нет картинки
                if len(caption) > 1000:
                    logger.warning('⚠️ Текст слишком длинный для подписи! Отправляем раздельно.')
                    if img_url:
                        await spy.client.send_message(mod_channel, file=img_url) # Только фото
                    await spy.client.send_message(mod_channel, caption) # Текст отдельно (до 4096 символов)
                else:
                    # Стандартный режим (фото + подпись)
                    if img_url:
                        await spy.client.send_message(mod_channel, caption, file=img_url)
                    else:
                        await spy.client.send_message(mod_channel, caption)
                
                await db.mark_as_published(news['id'])
                logger.info(f'✅ Опубликовано!')
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f'Ошибка отправки: {e}')
        
        logger.info('🏁 Готово.')

    except Exception as e:
        logger.critical(f'Сбой: {e}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())