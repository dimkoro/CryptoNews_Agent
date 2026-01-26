import aiohttp
import logging
import random
import io
import asyncio

logger = logging.getLogger('CryptoBot')

class ImageService:
    def __init__(self, provider, api_key=None, proxy=None, hf_key=None):
        self.provider = provider
        self.proxy = proxy
        self.styles = {
            'cyberpunk': ", cyberpunk style, neon lights, high tech, futuristic city background, cinematic lighting, 8k",
            'sketch': ", pencil sketch style, hand-drawn graphite, detailed cross-hatching, rough paper texture, black and white artistic",
            'realism': ", cinematic photography, hyperrealistic, 8k, ray tracing, unreal engine 5, dramatic lighting, highly detailed",
            'popart': ", pop art style, vibrant bold colors, comic book aesthetic, halftone dots, thick outlines, artistic masterpiece",
            'oil': ", oil painting style, textured brushstrokes, classical composition, dramatic light and shadow, artistic masterpiece"
        }
        logger.info(f'🎨 ImageService v16.14 (Custom Styles): {self.provider.upper()}')

    async def get_image(self, query, style_type='cyberpunk'):
        style_prompt = self.styles.get(style_type, self.styles['cyberpunk'])
        final_prompt = f"{query}{style_prompt}, high quality, no text"
        return await self._generate_pollinations(final_prompt)

    async def _generate_pollinations(self, prompt):
        try:
            encoded = prompt.replace(" ", "%20").replace("\n", "")
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1280&height=720&seed={seed}&nologo=true"
            return await self._download_image(url)
        except: return None

    async def _download_image(self, url):
        for i in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, proxy=self.proxy, timeout=60) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 2000: return io.BytesIO(data)
            except: await asyncio.sleep(2)
        return None
