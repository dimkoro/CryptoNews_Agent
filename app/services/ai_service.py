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
            
        # Склеиваем историю. Сравниваем СМЫСЛ, а не слова.
        history_block = "\n---\n".join(history_texts[:15])
        
        prompt = f'''Роль: Фильтр дубликатов новостей.
Задача: Ответь ДУБЛЬ, если новая новость описывает ТО ЖЕ СОБЫТИЕ, что и одна из старых.

НОВАЯ НОВОСТЬ:
{new_text[:800]}

ИСТОРИЯ (Уже опубликовано):
{history_block}

ВАЖНО: Если событие то же самое, но из другого источника — это ДУБЛЬ.
ОТВЕТ (Одно слово):'''

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            res = response.text.strip().upper()
            return 'ДУБЛЬ' in res or 'DUPLICATE' in res
        except Exception as e:
            logger.error(f'AI Check Error: {e}')
            return False

    async def rewrite_news(self, text, instruction=None):
        # ОБНОВЛЕННЫЙ ДИЗАЙН: Заголовок БОЛЬШОЙ, метки code-style
        base_prompt = '''Ты — редактор крипто-медиа.
Задача: Сделай рерайт новости для Telegram.

ДИЗАЙН:
1. Заголовок: Жирный, яркий, без слов "Заголовок" (**Текст**).
2. Подзаголовки "Суть" и "Контекст": Используй `моноширинный код` (`📊 Суть`).

ШАБЛОН:
**Яркий Кликбейтный Заголовок**

`📊 Суть`
Текст сути (2-3 предложения, факты)...

`💡 Контекст`
Текст вывода или влияния на рынок...

В КОНЦЕ: ||| <запрос фото>'''
        
        if instruction:
             prompt = f"{base_prompt}\nДОП. ИНСТРУКЦИЯ: {instruction}\n\nТЕКСТ:{text}"
        else:
             prompt = f"{base_prompt}\nОГРАНИЧЕНИЕ: 800 символов.\n\nТЕКСТ:{text}"

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            clean = response.text.replace("**ЗАГОЛОВОК**", "").strip()
            return clean
        except Exception as e:
            logger.error(f'AI Rewrite Error: {e}')
            return None