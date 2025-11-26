import google.generativeai as genai
import logging
import asyncio
import os

logger = logging.getLogger('CryptoBot')

class AIService:
    def __init__(self, api_key, proxy=None):
        if proxy:
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')

    async def rewrite_news(self, text):
        # ДОБАВИЛИ ОГРАНИЧЕНИЕ ПО ДЛИНЕ (800 символов)
        prompt = f'''Ты — профессиональный финансовый обозреватель.
Твоя задача: прочитать новость и написать краткую аналитическую сводку на русском языке.

ОГРАНИЧЕНИЕ: Итоговый текст должен быть НЕ БОЛЕЕ 800 символов (чтобы влезть в Telegram).

СТРУКТУРА ОТВЕТА:
1. 📰 ЗАГОЛОВОК
2. 📊 СУТЬ: 2-3 абзаца. Факты и цифры.
3. 💡 КОНТЕКСТ.

В КОНЦЕ ОТВЕТА добавь разделитель ||| и запрос для фото (физический объект).

ИСХОДНЫЙ ТЕКСТ:\n{text}'''
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            logger.error(f'AI Ошибка: {e}')
            return None