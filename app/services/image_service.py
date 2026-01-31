import aiohttp
import logging
import random
import aiofiles
import os
import asyncio

logger = logging.getLogger('CryptoBot')

class ImageService:
    def __init__(self, provider, api_key=None, proxy=None, hf_key=None):
        self.provider = provider
        self.proxy = proxy
        self.styles = {
            'cyberpunk': ", cyberpunk style, neon lights, futuristic city, cinematic 8k",
            'sketch': ", pencil sketch, detailed cross-hatching, black and white masterpiece",
            'realism': ", cinematic photography, hyperrealistic, ray tracing, dramatic lighting",
            'popart': ", pop art style, vibrant bold colors, comic book aesthetic, halftone dots",
            'oil': ", oil painting style, textured brushstrokes, classical composition"
        }
        os.makedirs('temp', exist_ok=True)
        logger.info(f'🎨 ImageService v17.0: {self.provider.upper()}')

    async def get_image(self, query, style_type='cyberpunk'):
        style = self.styles.get(style_type, self.styles['cyberpunk'])
        prompt = f"{query}{style}, high quality, no text"
        filename = f"temp/img_{random.randint(1000, 9999)}.jpg"
        
        if await self._generate_pollinations(prompt, filename):
            return filename
        return None

    async def _generate_pollinations(self, prompt, filename):
        safe_prompt = prompt[:200].replace(" ", "%20").replace("\n", "")
        seed = random.randint(1, 99999)
        strategies = [
            {'model': 'flux', 'timeout': 120, 'desc': 'Flux (HQ)'},
            {'model': 'flux', 'timeout': 120, 'desc': 'Flux (Retry)'},
            {'model': 'flux', 'timeout': 120, 'desc': 'Flux (Last try)'},
            {'model': 'turbo', 'timeout': 60, 'desc': '⚠️ Turbo (Fallback)'},
            {'model': 'turbo', 'timeout': 60, 'desc': '⚠️ Turbo (Last hope)'}
        ]
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

        for i, strat in enumerate(strategies):
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model={strat['model']}&width=1080&height=1350&seed={seed}&nologo=true"
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, proxy=self.proxy, timeout=strat['timeout']) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(filename, mode='wb') as f:
                                async for chunk in resp.content.iter_chunked(1024):
                                    await f.write(chunk)
                            if os.path.getsize(filename) > 1000:
                                if strat['model'] == 'turbo': logger.warning(f"🎨 Использован резерв Turbo.")
                                return True
            except Exception as e:
                logger.warning(f"🎨 Сбой {strat['desc']}: {e}")
            await asyncio.sleep(5 + (i * 2))
        return False