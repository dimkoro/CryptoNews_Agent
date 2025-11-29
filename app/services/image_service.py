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
        
        # ИСПРАВЛЕННЫЙ URL (ROUTER)
        self.hf_url = "https://router.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        self.unsplash_url = 'https://api.unsplash.com/search/photos'
        
        # СТИЛИ
        self.styles = [
            "cinematic 3d render, unreal engine 5, ray tracing, 8k",
            "cyberpunk style, neon lighting, dark background, futuristic",
            "ink illustration, cross-hatching, editorial newspaper art style, detailed",
            "oil painting, impasto brush strokes, dramatic lighting, masterpiece",
            "double exposure photography, artistic, minimalistic, clean background",
            "isometric 3d vector art, clean lines, vibrant colors, trending on behance"
        ]
        
        logger.info(f'🎨 ImageService: {self.provider.upper()} (SDXL Router Fix)')

    async def get_image(self, query):
        current_style = random.choice(self.styles)
        
        if self.provider == 'huggingface':
            # Пробуем HF, если ошибка -> Pollinations
            img = await self._generate_hf(query, current_style)
            if img:
                return img
            logger.warning("⚠️ HF сбой. Переход на Pollinations Flux...")
            return await self._generate_pollinations(query, current_style)
            
        elif self.provider == 'unsplash':
            return await self._get_unsplash_url(query)
            
        return await self._generate_pollinations(query, current_style)

    async def _generate_hf(self, query, style):
        if not self.hf_key: return None
        headers = {"Authorization": f"Bearer {self.hf_key}"}
        enhanced_prompt = f"(cinematic art:1.2), {query}, {style}, crypto currency theme, digital art, 8k, highly detailed"
        payload = {"inputs": enhanced_prompt}
        
        try:
            logger.info(f'🎨 HF SDXL рисует ({style.split(",")[0]}): "{query}"...')
            async with aiohttp.ClientSession() as session:
                async with session.post(self.hf_url, headers=headers, json=payload, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        file_obj = io.BytesIO(data)
                        file_obj.name = 'sdxl_art.jpg'
                        return file_obj
                    else:
                        logger.error(f'HF Error {resp.status}')
        except Exception as e:
            logger.error(f'HF Conn Error: {e}')
        return None

    async def _generate_pollinations(self, query, style):
        try:
            prompt = f"{query}, {style}, highly detailed"
            encoded = prompt.replace(" ", "%20")
            seed = random.randint(1, 99999)
            logger.info(f'🎨 Pollinations рисует ({style.split(",")[0]}): "{query}"...')
            url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1280&height=720&seed={seed}&nologo=true"
            return await self._download_image(url)
        except Exception as e:
            logger.error(f'Pollinations Error: {e}')
            return None

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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, proxy=self.proxy, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        file_obj = io.BytesIO(data)
                        file_obj.name = 'image.jpg'
                        return file_obj
        except Exception: pass
        return None