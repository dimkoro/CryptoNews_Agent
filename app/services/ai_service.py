import google.generativeai as genai
import logging
import asyncio
import os
import re
from PIL import Image
import io

logger = logging.getLogger('CryptoBot')

# СПИСОК ЛУЧШИХ МОДЕЛЕЙ (Из твоей диагностики)
# Бот будет пробовать их по очереди, пока не найдет рабочую
CANDIDATE_MODELS = [
    'models/gemini-2.0-flash-exp',
    'models/gemini-2.0-flash',
    'models/gemini-flash-latest',       # Это стабильная 1.5
    'models/gemini-flash-lite-latest'
]

class AIService:
    def __init__(self, api_key, proxy=None):
        if proxy:
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy
        genai.configure(api_key=api_key)
        self.model = None
        self.current_model_name = None

    async def pick_best_model(self):
        """Проверяет модели при старте и выбирает лучшую"""
        logger.info("🧠 Подбор оптимальной AI модели...")
        for model_name in CANDIDATE_MODELS:
            try:
                # Тестовый прогон (быстрый)
                test_model = genai.GenerativeModel(model_name)
                # Делаем тестовый запрос в отдельном потоке
                response = await asyncio.to_thread(
                    test_model.generate_content, "Hi", generation_config={'max_output_tokens': 1}
                )
                if response and response.text:
                    self.model = test_model
                    self.current_model_name = model_name
                    logger.info(f"✅ Выбрана модель: {model_name}")
                    return
            except Exception as e:
                logger.warning(f"⚠️ {model_name} недоступна: {e}")
                continue
        
        # Если ничего не подошло, ставим запасную
        logger.error("❌ Все модели недоступны! Ставлю gemini-1.5-flash наугад.")
        self.model = genai.GenerativeModel('models/gemini-1.5-flash')
        self.current_model_name = 'models/gemini-1.5-flash'

    async def _safe_generate(self, prompt, retries=3):
        if not self.model: await self.pick_best_model()
        
        for i in range(retries):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(self.model.generate_content, prompt),
                    timeout=60
                )
                return response.text
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ AI Timeout ({self.current_model_name}). Жду 10с...")
                await asyncio.sleep(10)
            except Exception as e:
                err = str(e)
                if "429" in err:
                    logger.warning(f"⚠️ Лимит (429) на {self.current_model_name}. Пауза 60с...")
                    await asyncio.sleep(60)
                elif "404" in err or "Not Found" in err:
                     logger.error(f"❌ Модель {self.current_model_name} умерла. Ищу новую...")
                     await self.pick_best_model()
                else:
                    logger.error(f"⚠️ Ошибка AI: {e}")
                    await asyncio.sleep(2)
        return None
    
    def clean_links(self, text):
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'\\[.*?\\]\\(.*?\\)', '', text)
        return text.strip()

    async def generate_variants(self, text):
        prompt = f'''Ты — редактор. Напиши 2 варианта поста.\nВАЖНО: БЕЗ ССЫЛОК.\n\n1. Хайповый (эмодзи).\n2. Строгий (факты).\n\nФОРМАТ:\n===VAR1===\n<Текст 1 с жирным заголовком>\n===VAR2===\n<Текст 2 с жирным заголовком>\n\nТЕКСТ:{text[:1500]}'''
        res = await self._safe_generate(prompt)
        if res and '===VAR1===' in res:
            parts = res.split('===VAR2===')
            v1 = self.clean_links(parts[0].replace('===VAR1===', '').strip())
            v2 = self.clean_links(parts[1].strip()) if len(parts)>1 else v1
            return v1, v2
        return None, None

    async def describe_image_for_remake(self, image_bytes):
        if not image_bytes: return "crypto concept"
        try:
            img = Image.open(io.BytesIO(image_bytes))
            prompt = "Describe this image for Stable Diffusion. 15 words max."
            response = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, [prompt, img]),
                timeout=45
            )
            return response.text.strip()
        except: return "crypto digital art"
            
    async def generate_image_prompt(self, text):
        res = await self._safe_generate(f"Stable Diffusion prompt for: {text[:300]}. 10 words.")
        return res.strip() if res else "crypto art"
        
    async def check_duplicate(self, text, history): 
        if not history: return False
        block = "\\n---\\n".join(history[:10])
        res = await self._safe_generate(f"Check duplicate. Answer DUPLICATE or UNIQUE.\\nNEW:{text[:500]}\\nHISTORY:{block}")
        return res and 'DUPLICATE' in res.upper()
