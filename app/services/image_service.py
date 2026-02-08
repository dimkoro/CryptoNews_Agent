import aiohttp
import logging
import random
import aiofiles
import os
import asyncio
import io
from urllib.parse import quote
from PIL import Image
from huggingface_hub import InferenceClient

logger = logging.getLogger('CryptoBot')


class ImageService:
    def __init__(
        self,
        provider,
        api_key=None,
        proxy=None,
        hf_key=None,
        hf_model=None,
        hf_width=768,
        hf_height=960,
        fallback_list=None,
        pollinations_base_url=None,
        pollinations_model=None,
        pollinations_width=768,
        pollinations_height=960,
        pollinations_retries=3,
        pollinations_timeout=60
    ):
        self.provider = (provider or 'auto').strip().lower()
        self.proxy = proxy
        self.unsplash_key = api_key
        self.hf_key = hf_key
        self.hf_model = hf_model or 'runwayml/stable-diffusion-v1-5'
        self.hf_width = hf_width
        self.hf_height = hf_height
        self.hf_client = InferenceClient(token=self.hf_key) if self.hf_key else None
        self.pollinations_base_url = (pollinations_base_url or 'https://image.pollinations.ai/prompt/').rstrip('/') + '/'
        self.pollinations_model = pollinations_model or 'flux'
        self.pollinations_width = pollinations_width
        self.pollinations_height = pollinations_height
        self.pollinations_retries = max(1, int(pollinations_retries))
        self.pollinations_timeout = max(10, int(pollinations_timeout))
        self._pollinations_flux_failures = 0
        # aHash blacklist for known placeholder images (e.g., Pollinations "moved" notice)
        self._ahash_blacklist = {
            0x007eff462e260000
        }
        if fallback_list:
            self.fallbacks = [p.strip().lower() for p in fallback_list.split(',') if p.strip()]
        else:
            self.fallbacks = ['pollinations', 'huggingface', 'unsplash']
        self.styles = {
            'cyberpunk': ", cyberpunk style, neon lights, futuristic city, cinematic 8k",
            'sketch': ", pencil sketch, detailed cross-hatching, black and white masterpiece",
            'realism': ", cinematic photography, hyperrealistic, ray tracing, dramatic lighting",
            'popart': ", pop art style, vibrant bold colors, comic book aesthetic, halftone dots",
            'oil': ", oil painting style, textured brushstrokes, classical composition"
        }
        os.makedirs('media', exist_ok=True)
        logger.info(f'ImageService v17.4: {self.provider.upper()}')

    async def get_image(self, query, style_type='cyberpunk'):
        style = self.styles.get(style_type, self.styles['cyberpunk'])
        prompt = f"{query}{style}, high quality, no text"
        filename = f"media/img_{random.randint(1000, 9999)}.jpg"
        base_query = (query or '').strip()[:120]

        providers = self.fallbacks if self.provider == 'auto' else [self.provider]
        for prov in providers:
            ok = await self._generate_with_provider(prov, prompt, base_query, filename)
            if ok:
                logger.info(f"Image provider success: {prov}")
                return filename
        return None

    async def _generate_with_provider(self, provider, prompt, base_query, filename):
        if provider in ('ai', 'pollinations', 'pollinations.ai'):
            return await self._generate_pollinations(prompt, filename)
        if provider == 'huggingface':
            return await self._generate_huggingface(prompt, filename)
        if provider == 'unsplash':
            return await self._generate_unsplash(base_query, filename)
        logger.warning(f"Image provider not supported: {provider}")
        return False

    def _normalize_and_save(self, data, filename):
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        if img.size != (1080, 1350):
            img = img.resize((1080, 1350), Image.LANCZOS)
        if self._is_blacklisted_image(img):
            return False
        img.save(filename, format="JPEG", quality=92)
        return True

    def _normalize_and_save_image(self, img, filename):
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.size != (1080, 1350):
            img = img.resize((1080, 1350), Image.LANCZOS)
        if self._is_blacklisted_image(img):
            return False
        img.save(filename, format="JPEG", quality=92)
        return True

    def _is_blacklisted_image(self, img):
        try:
            ah = self._ahash(img)
            return ah in self._ahash_blacklist
        except Exception:
            return False

    def _ahash(self, img):
        # 8x8 aHash
        g = img.convert("L").resize((8, 8), Image.LANCZOS)
        pixels = list(g.getdata())
        avg = sum(pixels) / len(pixels)
        value = 0
        for p in pixels:
            value = (value << 1) | int(p > avg)
        return value

    async def _generate_pollinations(self, prompt, filename):
        safe_prompt = quote(prompt[:200].replace("\n", ""), safe="")
        seed = random.randint(1, 99999)
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
        }

        for i in range(self.pollinations_retries):
            model = self.pollinations_model
            if model == 'flux' and self._pollinations_flux_failures >= 3:
                model = 'turbo'
            url = (
                f"{self.pollinations_base_url}{safe_prompt}"
                f"?model={model}&width={self.pollinations_width}"
                f"&height={self.pollinations_height}&seed={seed}&nologo=true"
            )
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, proxy=self.proxy, timeout=self.pollinations_timeout) as resp:
                        if resp.status == 200:
                            ctype = resp.headers.get('Content-Type', '')
                            data = await resp.read()
                            if not data:
                                logger.warning("Empty response from generator.")
                                continue
                            if ctype and not ctype.startswith('image/'):
                                logger.warning(f"Non-image response: {ctype}")
                                continue
                            try:
                                saved = self._normalize_and_save(data, filename)
                                if saved is False:
                                    logger.warning("Image matched blacklist; retrying provider.")
                                    continue
                            except Exception:
                                async with aiofiles.open(filename, mode='wb') as f:
                                    await f.write(data)

                            if os.path.getsize(filename) > 1000:
                                if model == 'flux':
                                    self._pollinations_flux_failures = 0
                                return True
                            logger.warning("Generated file too small.")
                        else:
                            logger.warning(f"HTTP {resp.status} from generator.")
            except Exception as e:
                logger.warning(f"Pollinations error: {e}")
            if model == 'flux':
                self._pollinations_flux_failures += 1
            await asyncio.sleep(2 + (i * 2) + random.random())
        return False

    async def _generate_huggingface(self, prompt, filename):
        if not self.hf_client:
            logger.warning("HUGGINGFACE_KEY not set. Skipping HF.")
            return False

        def _call():
            try:
                return self.hf_client.text_to_image(
                    prompt,
                    model=self.hf_model,
                    width=self.hf_width,
                    height=self.hf_height
                )
            except StopIteration:
                return None

        for i in range(3):
            try:
                img = await asyncio.to_thread(_call)
                if img is None:
                    logger.warning("HF returned empty response.")
                    continue
                if isinstance(img, Image.Image):
                    saved = self._normalize_and_save_image(img, filename)
                    if saved is False:
                        logger.warning("Image matched blacklist; retrying provider.")
                        continue
                else:
                    saved = self._normalize_and_save(img, filename)
                    if saved is False:
                        logger.warning("Image matched blacklist; retrying provider.")
                        continue
                if os.path.getsize(filename) > 1000:
                    return True
                logger.warning("HF generated file too small.")
            except Exception as e:
                logger.warning(f"HF error: {e}")
            await asyncio.sleep(6 + (i * 3))
        return False

    async def _generate_unsplash(self, query, filename):
        if not self.unsplash_key:
            logger.warning("UNSPLASH_ACCESS_KEY not set. Skipping Unsplash.")
            return False

        queries = [q for q in [query, "crypto", "bitcoin"] if q]
        headers = {"Authorization": f"Client-ID {self.unsplash_key}"}

        for q in queries:
            safe_query = quote(q[:120], safe="")
            url = (
                "https://api.unsplash.com/search/photos"
                f"?query={safe_query}&orientation=portrait&per_page=1&content_filter=high"
            )

            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, proxy=self.proxy, timeout=60) as resp:
                        if resp.status != 200:
                            err = await resp.text()
                            logger.warning(f"Unsplash HTTP {resp.status}: {err}")
                            continue
                        data = await resp.json()
                        total = data.get('total', 0)
                        results = data.get('results', [])
                        if total == 0 or not results:
                            logger.warning(f"Unsplash: no photos for '{q}'.")
                            continue
                        img_url = results[0].get('urls', {}).get('regular') or results[0].get('urls', {}).get('full')
                        if not img_url:
                            logger.warning("Unsplash: no image URL.")
                            continue
                    async with session.get(img_url, proxy=self.proxy, timeout=60) as img_resp:
                        if img_resp.status != 200:
                            logger.warning(f"Unsplash image HTTP {img_resp.status}.")
                            continue
                        img_data = await img_resp.read()
                        if not img_data:
                            logger.warning("Unsplash: empty image response.")
                            continue
                        try:
                            saved = self._normalize_and_save(img_data, filename)
                            if saved is False:
                                logger.warning("Image matched blacklist; retrying provider.")
                                continue
                        except Exception:
                            async with aiofiles.open(filename, mode='wb') as f:
                                await f.write(img_data)
                    return os.path.exists(filename) and os.path.getsize(filename) > 1000
            except Exception as e:
                logger.warning(f"Unsplash error: {e}")
                continue

        return False
