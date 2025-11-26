import asyncio
import sys
from app.core.logger import setup_logger
from app.core.config import load_config
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService

logger = setup_logger()

async def main():
    try:
        logger.info('--- ЗАПУСК УМНОГО ЦИКЛА v2 ---')
        config = load_config()
        
        spy = TelegramSpy(config)
        ai = AIService(config['gemini_key'], config['proxy'])
        img = ImageService(config['unsplash_key'], config['proxy'])
        
        await spy.start_spy()
        
        # Берем первый канал
        with open('channels.txt', 'r') as f:
            target_channel = f.readline().strip()
        
        logger.info(f'📡 Сканируем: {target_channel}')
        entity = await spy.client.get_entity(target_channel)
        messages = await spy.client.get_messages(entity, limit=3)
        
        news_text = None
        for msg in messages:
            if msg.text and len(msg.text) > 150:
                news_text = msg.text
                break
        
        if not news_text:
            logger.error('Нет подходящих новостей.')
            return

        # ОБРАБОТКА AI
        logger.info('🧠 Gemini думает над текстом и картинкой...')
        ai_response = await ai.rewrite_news(news_text)
        
        if not ai_response:
            return

        # РАЗДЕЛЯЕМ ОТВЕТ (Текст отдельно, Запрос отдельно)
        if '|||' in ai_response:
            final_text, image_query = ai_response.split('|||')
            final_text = final_text.strip()
            image_query = image_query.strip()
            logger.info(f'🔎 AI придумал запрос для фото: "{image_query}"')
        else:
            # Если AI забыл разделитель (бывает), берем просто текст
            final_text = ai_response
            image_query = 'crypto news'
            
        # ПОИСК КАРТИНКИ
        image_url = await img.get_image(image_query)
        
        # ОТПРАВКА
        mod_channel = int(config['mod_channel'])
        caption = final_text + '\n\n🤖 #CryptoAgent #Moderation'
        
        if image_url:
            await spy.client.send_message(mod_channel, caption, file=image_url)
        else:
            await spy.client.send_message(mod_channel, caption)
            
        logger.info('✅ Готово! Проверяй канал модерации.')

    except Exception as e:
        logger.critical(f'Сбой: {e}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())