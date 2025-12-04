import google.generativeai as genai
import logging
import asyncio
import os
import re
from PIL import Image
import io

logger = logging.getLogger('CryptoBot')

class AIService:
    def __init__(self, api_key, proxy=None):
        if proxy:
            os.environ['http_proxy'] = proxy
            os.environ['https_proxy'] = proxy
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')

    async def _safe_generate(self, prompt, retries=3):
        for i in range(retries):
            try:
                response = await asyncio.to_thread(self.model.generate_content, prompt)
                return response.text
            except Exception as e:
                if "429" in str(e): await asyncio.sleep(60)
                else: return None
        return None
    
    def clean_links(self, text):
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)
        return text.strip()

    async def generate_variants(self, text):
        prompt = f'''Ты — редактор. Напиши 2 варианта поста.
ВАЖНО: БЕЗ ССЫЛОК.

1. Хайповый (эмодзи).
2. Строгий (факты).

ФОРМАТ:
===VAR1===
<Текст 1 с жирным заголовком>
===VAR2===
<Текст 2 с жирным заголовком>

ТЕКСТ:{text[:1500]}'''
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
            response = await asyncio.to_thread(self.model.generate_content, [prompt, img])
            return response.text.strip()
        except: return "crypto digital art"
            
    async def generate_image_prompt(self, text):
        res = await self._safe_generate(f"Stable Diffusion prompt for: {text[:300]}. 10 words.")
        return res.strip() if res else "crypto art"
        
    async def check_duplicate(self, text, history): 
        if not history: return False
        block = "\n---\n".join(history[:10])
        res = await self._safe_generate(f"Check duplicate. Answer DUPLICATE or UNIQUE.\nNEW:{text[:500]}\nHISTORY:{block}")
        return res and 'DUPLICATE' in res.upper()