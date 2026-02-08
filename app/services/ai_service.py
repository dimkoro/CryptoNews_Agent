import os
import logging
import asyncio
import re
from google import genai
from google.genai import types
from PIL import Image
import io

logger = logging.getLogger('CryptoBot')

PRIORITY_MODELS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-2.0-flash-exp',
    'gemini-1.5-flash',
    'gemini-flash-latest'
]


class AIService:
    def __init__(self, api_key, proxy=None):
        if proxy:
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy

        self.client = genai.Client(api_key=api_key)
        self.current_model = None
        self.model_blacklist = set()

    async def check_model_health(self, model_name):
        try:
            await asyncio.to_thread(
                self.client.models.generate_content,
                model=model_name,
                contents="Hi",
                config=types.GenerateContentConfig(max_output_tokens=1)
            )
            return True
        except Exception:
            return False

    async def pick_best_model(self):
        logger.info("🧠 AI: Диагностика моделей...")
        for model in PRIORITY_MODELS:
            if model in self.model_blacklist:
                continue
            if await self.check_model_health(model):
                self.current_model = model
                logger.info(f"✅ AI: Выбрана модель {self.current_model}")
                return

        try:
            all_models = await asyncio.to_thread(self.client.models.list)
            for m in all_models:
                name = m.name.replace('models/', '')
                if 'generateContent' in (m.supported_actions or []) and 'gemini' in name:
                    if name in self.model_blacklist:
                        continue
                    if await self.check_model_health(name):
                        self.current_model = name
                        logger.info(f"⚠️ AI: Резерв {name}")
                        return
        except Exception as e:
            logger.error(f"List Err: {e}")

        self.current_model = 'gemini-1.5-flash'
        logger.warning(f"❌ AI: Дефолт {self.current_model}")

    async def _switch_model(self):
        if self.current_model:
            self.model_blacklist.add(self.current_model)
        self.current_model = None
        await self.pick_best_model()

    async def _generate_with_retries(self, prompt, tokens, attempts):
        for i in range(attempts):
            res = await self._safe_generate(prompt, tokens=tokens)
            if res:
                return res
            logger.warning(f"⚠️ AI: пустой ответ. Попытка {i+1}/{attempts}.")
            await asyncio.sleep(10)
        return None

    async def _safe_generate(self, prompt, tokens=1000, attempt=1):
        if not self.current_model:
            await self.pick_best_model()

        try:
            config = types.GenerateContentConfig(
                max_output_tokens=tokens,
                temperature=0.7,
                safety_settings=[
                    types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE')
                ]
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.current_model,
                contents=prompt,
                config=config
            )

            if response.text:
                return response.text
            else:
                if response.candidates and response.candidates[0].content.parts:
                    text_part = response.candidates[0].content.parts[0].text
                    if text_part:
                        return text_part
                logger.warning(f"⚠️ AI вернул пустоту. Response: {response}")
                return None

        except Exception as e:
            err = str(e)
            if "429" in err or "Resource exhausted" in err or "10054" in err or "ConnectionReset" in err or "reset by peer" in err or "disconnected" in err:
                if attempt < 5:
                    wait_time = 10 * attempt
                    logger.warning(f"🔄 Сбой ({self.current_model}). Жду {wait_time}с...")

                    if attempt >= 2:
                        logger.info("♻️ Принудительная смена модели...")
                        self.current_model = None

                    await asyncio.sleep(wait_time)
                    return await self._safe_generate(prompt, tokens, attempt + 1)
                else:
                    logger.error("❌ AI: Все попытки исчерпаны.")
            else:
                logger.error(f"AI Error: {e}")
            return None

    async def describe_image_for_remake(self, image_bytes):
        if not image_bytes:
            return "digital crypto art"
        try:
            if hasattr(image_bytes, 'seek'):
                image_bytes.seek(0)
            data = image_bytes.read() if hasattr(image_bytes, 'read') else image_bytes
            img = Image.open(io.BytesIO(data))
            prompt = [
                "Describe the visual content of this image in English. Focus on main subjects, colors, lighting and composition. Be descriptive but concise.",
                img
            ]
            res = await self._safe_generate(prompt, tokens=500)
            if res:
                logger.info(f"👁 AI: {res[:40]}...")
                return res.strip()
            return "crypto scene"
        except Exception as e:
            logger.warning(f"Vision Err: {e}")
            return "crypto art"

    async def generate_variants(self, text):
        prompt = f"""
РОЛЬ: Ты профессиональный редактор русскоязычного крипто-СМИ.
ЗАДАЧА: Переведи новость на русский язык и адаптируй её в 2 стиля, строго следуя примерам.

ПРИМЕР 1 (СТИЛЬ ХАЙП):
ПОЧЕМУ БИТКОИН ПАДАЕТ? ВИНОВАТ КЕВИН ВАРШ! 😱

Биткоин рухнул почти до $81 000! 📉 Все из-за того, что шансы Кевина Варша стать главой ФРС резко возросли! 🐻 Инвесторы в панике? Продаем все?

#Биткоин #Криптопаника #Bitcoin #CryptoCrash

ПРИМЕР 2 (СТИЛЬ РБК):
BINANCE ПЕРЕВЕДЕТ $1 МЛРД ИЗ SAFU В БИТКОИН

📊 Суть: Binance объявила о конвертации резервов своего фонда SAFU в размере около 1 миллиарда долларов США в BTC в течение следующих 30 дней. Компания планирует пополнить фонд до 1 миллиарда долларов, если Bitcoin упадет ниже 80 000 долларов США.
💡 Контекст: Это решение может оказать значительное влияние на рынок Bitcoin, потенциально увеличив его цену и ликвидность.

#Криптовалюта #Бинанс #Crypto #Binance

---
ТВОЕ ЗАДАНИЕ:
ИСХОДНАЯ НОВОСТЬ (EN):
{text[:2000]}

ТРЕБОВАНИЯ:
1. Язык: ТОЛЬКО РУССКИЙ.
2. Тэги: 2 на русском, 2 на английском.
3. Формат: Строго соблюдай разметку ===VAR1=== и ===VAR2===.

ФОРМАТ ОТВЕТА:
===VAR1===
(Твой вариант ХАЙП на русском)
===VAR2===
(Твой вариант РБК на русском)
"""
        res = await self._generate_with_retries(prompt, tokens=2000, attempts=3)
        if not res:
            await self._switch_model()
            res = await self._generate_with_retries(prompt, tokens=2000, attempts=2)
        if not res:
            await self._switch_model()
            res = await self._generate_with_retries(prompt, tokens=2000, attempts=2)

        if res and '===VAR1===' in res:
            try:
                c = res.split('===VAR1===')[1]
                p = c.split('===VAR2===')
                return re.sub(r'http\\S+', '', p[0].strip()), re.sub(r'http\\S+', '', p[1].strip())
            except Exception:
                pass
        return text[:800], text[:800]

    async def generate_image_prompt(self, text):
        res = await self._safe_generate(
            f"Create a visual prompt for an AI image generator based on this news: '{text[:400]}'. "
            "Write in English. Describe the scene, lighting, and style. Max 30 words. No text inside image.",
            tokens=200
        )
        return res.strip() if res else "crypto concept art"

    async def check_duplicate(self, text, history):
        if not history:
            return False
        block = "\n---\n".join(history[:15])
        res = await self._safe_generate(
            f"TASK: Check for duplicates.\nNEW NEWS: {text[:600]}\nHISTORY: {block}\n"
            "Compare events. Reply 'DUPLICATE' if same event, 'UNIQUE' if new.",
            tokens=20
        )
        return res and 'DUPLICATE' in res.upper()
