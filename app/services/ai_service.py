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

    async def _safe_generate(self, prompt, retries=3):
        """Метод с защитой от ошибки 429 (Лимиты)"""
        for i in range(retries):
            try:
                response = await asyncio.to_thread(self.model.generate_content, prompt)
                return response.text
            except Exception as e:
                if "429" in str(e):
                    wait_time = 60 # Ждем минуту, если Google ругается
                    logger.warning(f"⚠️ Лимит Google (429). Жду {wait_time} сек (Попытка {i+1}/{retries})...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f'AI Ошибка: {e}')
                    return None
        return None

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
        
        response_text = await self._safe_generate(prompt)
        if response_text:
            return 'ДУБЛЬ' in response_text.strip().upper()
        return False

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
        
        limit_instruction = "\nОГРАНИЧЕНИЕ: СТРОГО ДО 800 СИМВОЛОВ!"
        
        if instruction:
             prompt = f"{base_prompt}\nДОП. ИНСТРУКЦИЯ: {instruction}{limit_instruction}\n\nТЕКСТ:{text}"
        else:
             prompt = f"{base_prompt}{limit_instruction}\n\nТЕКСТ:{text}"

        response_text = await self._safe_generate(prompt)
        if response_text:
            clean = response_text.replace("<", "").replace(">", "").replace("**ЗАГОЛОВОК**", "").strip()
            return clean
        return None

    async def generate_image_prompt(self, text):
        prompt = f'''Прочитай новость и придумай описание картинки для генератора (Stable Diffusion).
Задача: Визуальная метафора или сцена.
Язык: Английский.
Длина: 10-15 слов.

НОВОСТЬ:
{text[:500]}

ОТВЕТ (Только описание):'''
        
        response_text = await self._safe_generate(prompt)
        if response_text:
            return response_text.strip()
        return "crypto technology abstract"