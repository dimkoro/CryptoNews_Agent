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

В КОНЦЕ: ||| <запрос фото>'''
        
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

    async def generate_image_prompt(self, text):
        # МЕТОД v9.0: Умный промпт
        prompt = f'''Прочитай новость и придумай описание картинки для генератора (Stable Diffusion).
Задача: Визуальная метафора или сцена.
Язык: Английский.
Длина: 10-15 слов.

НОВОСТЬ:
{text[:500]}

ОТВЕТ (Только описание):'''
        
        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f'Img Prompt Error: {e}')
            return "crypto technology abstract"