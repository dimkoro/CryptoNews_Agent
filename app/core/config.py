import os
import json
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    required_vars = [
        'API_ID',
        'API_HASH',
        'BOT_TOKEN',
        'GEMINI_API_KEY',
        'PUB_CHANNEL_ID',
        'MOD_CHANNEL_ID'
    ]
    missing = [key for key in required_vars if not os.getenv(key)]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(
            f"Отсутствуют обязательные переменные в .env: {missing_list}. "
            "Заполни их и перезапусти бота."
        )
    return {
        'api_id': int(os.getenv('API_ID')),
        'api_hash': os.getenv('API_HASH'),
        'bot_token': os.getenv('BOT_TOKEN'),
        'gemini_key': os.getenv('GEMINI_API_KEY'),
        'unsplash_key': os.getenv('UNSPLASH_ACCESS_KEY'),
        'hf_key': os.getenv('HUGGINGFACE_KEY'),
        'pub_channel': int(os.getenv('PUB_CHANNEL_ID')),
        'mod_channel': int(os.getenv('MOD_CHANNEL_ID')),
        'image_provider': os.getenv('IMAGE_PROVIDER', 'auto'),
        'image_fallbacks': os.getenv('IMAGE_FALLBACKS', 'pollinations,huggingface,unsplash'),
        'hf_model': os.getenv('HF_IMAGE_MODEL', 'runwayml/stable-diffusion-v1-5'),
        'hf_width': int(os.getenv('HF_IMAGE_WIDTH', '768')),
        'hf_height': int(os.getenv('HF_IMAGE_HEIGHT', '960')),
        'proxy': os.getenv('PROXY_URL', None),
        'style_1': os.getenv('STYLE_IMG_1', 'cyberpunk'),
        'style_2': os.getenv('STYLE_IMG_2', 'sketch'),
        'style_remake': os.getenv('STYLE_REMAKE', 'realism'),
        'channel_signature': os.getenv('CHANNEL_SIGNATURE', '@CryptoNews'),
        'channel_url': os.getenv('CHANNEL_URL', None),
        'pollinations_base_url': os.getenv('POLLINATIONS_BASE_URL', 'https://image.pollinations.ai/prompt/'),
        'pollinations_model': os.getenv('POLLINATIONS_MODEL', 'flux'),
        'pollinations_width': int(os.getenv('POLLINATIONS_WIDTH', '768')),
        'pollinations_height': int(os.getenv('POLLINATIONS_HEIGHT', '960')),
        'pollinations_retries': int(os.getenv('POLLINATIONS_RETRIES', '3')),
        'pollinations_timeout': int(os.getenv('POLLINATIONS_TIMEOUT', '60'))
    }
