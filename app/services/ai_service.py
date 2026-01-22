import google.generativeai as genai
import logging
import asyncio
import os
import re
from PIL import Image
import io

logger = logging.getLogger('CryptoBot')

CANDIDATE_MODELS = [
    'models/gemini-2.0-flash-exp',
    'models/gemini-2.0-flash',
    'models/gemini-flash-latest'
]

class AIService:
    def __init__(self, api_key, proxy=None):
        if proxy:
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy
        genai.configure(api_key=api_key)
        self.model = None

    async def pick_best_model(self):
        logger.info("🧠 Подбор оптимальной AI модели...")
        for model_name in CANDIDATE_MODELS:
            try:
                test_model = genai.GenerativeModel(model_name)
                res = await asyncio.to_thread(test_model.generate_content, "Hi", generation_config={'max_output_tokens': 1})
                if res: self.model = test_model; return
            except: continue
        self.model = genai.GenerativeModel('models/gemini-1.5-flash')

    async def _safe_generate(self, prompt, tokens=1000):
        if not self.model: await self.pick_best_model()
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, prompt, generation_config={'max_output_tokens': tokens}),
                timeout=40
            )
            return res.text
        except: return None

    async def describe_image_for_remake(self, image_bytes):
        if not image_bytes: return "digital crypto art"
        try:
            if hasattr(image_bytes, 'seek'): image_bytes.seek(0)
            data = image_bytes.read() if hasattr(image_bytes, 'read') else image_bytes
            img = Image.open(io.BytesIO(data))
            prompt = "Describe the visual content of this image in detail. Focus on people, lighting, and composition. 40 words max."
            res = await self._safe_generate([prompt, img], tokens=150)
            if res: logger.info(f"👁 AI УВИДЕЛ: {res[:60]}...")
            return res if res else "crypto scene"
        except Exception as e: 
            logger.warning(f"AI Vision Error: {e}")
            return "crypto art"

    async def generate_variants(self, text):
        # ПРОФЕССИОНАЛЬНЫЙ ПРОМПТ v15.9
        prompt = f"""
Ты — главный редактор крипто-СМИ. Твоя задача — переписать новость в 2 форматах.

ИСХОДНЫЙ ТЕКСТ:
{text[:2000]}

=== ФОРМАТ 1: ХАЙП (Для Telegram) ===
1. ЗАГОЛОВОК: Кликбейтный, КРИЧАЩИЙ, ВЕСЬ КАПСОМ.
2. СТРУКТУРА: Заголовок -> Пустая строка -> Эмоциональный текст с эмодзи. Сленг (туземун, хомяки) разрешен.
Пример начала: "🔥 БИТКОИН СНОВА В ИГРЕ!\n\nРебята, вы видели этот график?!"

=== ФОРМАТ 2: СТРОГИЙ (Стиль РБК/Коммерсант) ===
1. ЗАГОЛОВОК: Информативный, деловой, ВЕСЬ КАПСОМ. Без эмодзи в заголовке.
2. СТРУКТУРА:
   - ЗАГОЛОВОК
   - (Пустая строка)
   - 📊 Суть: (1-2 предложения, самая соль)
   - 💡 Контекст: (Почему это важно, предыстория, аналитика)

ФОРМАТ ОТВЕТА (Строго соблюдай разделители):
===VAR1===
ЗАГОЛОВОК CAPS LOCK

Текст хайп...
===VAR2===
ЗАГОЛОВОК CAPS LOCK

📊 Суть: ...
💡 Контекст: ...
"""
        res = await self._safe_generate(prompt)
        
        if res and '===VAR1===' in res:
            try:
                content = res.split('===VAR1===')[1]
                parts = content.split('===VAR2===')
                v1 = re.sub(r'http\S+', '', parts[0].strip())
                v2 = re.sub(r'http\S+', '', parts[1].strip())
                return v1, v2
            except: pass
                
        return text[:800], text[:800]

    async def generate_image_prompt(self, text):
        prompt = f"Visual scene description for: {text[:400]}. Focus on main subject. 15 words max. No text."
        res = await self._safe_generate(prompt, tokens=50)
        return res.strip() if res else "crypto concept art"
        
    async def check_duplicate(self, text, history): 
        if not history: return False
        block = "\n---\n".join(history[:10])
        res = await self._safe_generate(f"Reply UNIQUE or DUPLICATE. New: {text[:500]}. History: {block}", tokens=10)
        return res and 'DUPLICATE' in res.upper()
