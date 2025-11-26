import aiohttp
import logging

logger = logging.getLogger('CryptoBot')

class ImageService:
    def __init__(self, api_key, proxy=None):
        self.api_key = api_key
        self.proxy = proxy
        self.base_url = 'https://api.unsplash.com/search/photos'

    async def get_image(self, query):
        if not self.api_key or 'skip' in self.api_key:
            return None
            
        headers = {'Authorization': f'Client-ID {self.api_key}'}
        params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
        
        try:
            # Передаем прокси внутрь запроса
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, headers=headers, params=params, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['results']:
                            return data['results'][0]['urls']['regular']
                    else:
                        logger.error(f'Unsplash ошибка: {resp.status}')
                        return None
        except Exception as e:
            logger.error(f'Image ошибка: {e}')
            return None