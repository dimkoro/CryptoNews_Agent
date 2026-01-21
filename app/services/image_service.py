import aiohttp
import logging
import random
import io
import asyncio

logger = logging.getLogger('CryptoBot')

class ImageService:
    def __init__(self, provider, api_key=None, proxy=None, hf_key=None):
        self.provider = provider
        self.api_key = api_key
        self.hf_key = hf_key
        self.proxy = proxy
        self.hf_url = "https://router.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        self.unsplash_url = 'https://api.unsplash.com/search/photos'
        self.styles = [
            "cinematic 3d render, unreal engine 5, 8k",
            "cyberpunk style, neon lighting, futuristic",
            "ink illustration, cross-hatching, editorial art",
            "oil painting, impasto brush strokes, dramatic lighting",
            "double exposure photography, artistic, minimalistic",
            "isometric 3d vector art, clean lines, vibrant colors"
        ]
        logger.info(f'🎨 ImageService v13.1 (Retries): {self.provider.upper()}')

    async def get_image(self, query):
        current_style = random.choice(self.styles)
        if self.provider == 'huggingface':
            img = await self._generate_hf(query, current_style)
            if img: return img
            logger.warning("⚠️ HF Fail -> Pollinations")
            return await self._generate_pollinations(query, current_style)
        elif self.provider == 'unsplash':
            return await self._get_unsplash_url(query)
        return await self._generate_pollinations(query, current_style)

    async def _generate_hf(self, query, style):
        if not self.hf_key: return None
        headers = {"Authorization": f"Bearer {self.hf_key}"}
        prompt = f"{query}, {style}, crypto theme, no text, 8k"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.hf_url, headers=headers, json={"inputs": prompt}, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return io.BytesIO(data)
        except: pass
        return None

    async def _generate_pollinations(self, query, style):
        try:
            prompt = f"{query}, {style}".replace(" ", "%20")
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{prompt}?model=flux&width=1280&height=720&seed={seed}&nologo=true"
            return await self._download_image(url)
        except: return None

    async def _get_unsplash_url(self, query):
        if not self.api_key: return None
        headers = {'Authorization': f'Client-ID {self.api_key}'}
        params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.unsplash_url, headers=headers, params=params, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['results']:
                            url = data['results'][0]['urls']['regular']
                            return await self._download_image(url)
        except Exception: pass
        return None

    async def _download_image(self, url):
        # ИСПРАВЛЕНИЕ: 3 попытки скачивания с паузами
        headers = {'User-Agent': 'Mozilla/5.0'}
        for i in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, proxy=self.proxy, timeout=60) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) < 1000: # Защита от битых файлов (меньше 1кб)
                                logger.warning(f'⚠️ Image too small ({len(data)}b). Retrying...')
                                await asyncio.sleep(2)
                                continue
                            return io.BytesIO(data)
                        else:
                            logger.warning(f'⚠️ DL Fail ({resp.status}). Try {i+1}/3')
            except Exception as e:
                logger.warning(f'⚠️ DL Err ({e}). Try {i+1}/3')
            await asyncio.sleep(3) # Пауза перед следующей попыткой
        
        logger.error("❌ Failed to download image after 3 attempts.")
        return None
