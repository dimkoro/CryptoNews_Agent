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

    async def check_duplicate(self, new_text, history_texts):
        if not history_texts:
            return False
        history_block = "\n---\n".join(history_texts[:15])
        prompt = f'''Роль: Фильтр дубликатов.
Задача: Ответь ДУБЛЬ, если новость описывает ТО ЖЕ СОБЫТИЕ.

НОВАЯ:
{new_text[:800]}

ИСТОРИЯ:
{history_block}

ОТВЕТ (ДУБЛЬ или УНИКАЛЬНО):'''
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return 'ДУБЛЬ' in response.text.strip().upper()
        except Exception: return False

    async def rewrite_news(self, text, instruction=None):
        base_prompt = '''Ты — редактор Telegram-канала.
Задача: Рерайт новости.

ФОРМАТ:
1. Заголовок жирным (**Текст**).
2. Подзаголовки "Суть" и "Контекст" как код (`Суть`).

ШАБЛОН:
**Заголовок**

`📊 Суть`
Текст...

`💡 Контекст`
Текст...

В КОНЦЕ: ||| description of image in english'''
        
        # ИСПРАВЛЕНИЕ: Добавляем лимит и в инструкцию редактирования
        limit_instruction = "\nОГРАНИЧЕНИЕ: СТРОГО ДО 800 СИМВОЛОВ!"
        
        if instruction:
             prompt = f"{base_prompt}\nДОП. ИНСТРУКЦИЯ: {instruction}{limit_instruction}\n\nТЕКСТ:{text}"
        else:
             prompt = f"{base_prompt}{limit_instruction}\n\nТЕКСТ:{text}"

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            clean = response.text.replace("<", "").replace(">", "").replace("**ЗАГОЛОВОК**", "").strip()
            return clean
        except Exception as e:
            logger.error(f'AI Error: {e}')
            return None