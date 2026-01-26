import os
import json
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    return {
        'api_id': int(os.getenv('API_ID')),
        'api_hash': os.getenv('API_HASH'),
        'bot_token': os.getenv('BOT_TOKEN'),
        'gemini_key': os.getenv('GEMINI_API_KEY'),
        'unsplash_key': os.getenv('UNSPLASH_ACCESS_KEY'),
        'hf_key': os.getenv('HUGGINGFACE_KEY'),
        'pub_channel': int(os.getenv('PUB_CHANNEL_ID')),
        'mod_channel': int(os.getenv('MOD_CHANNEL_ID')),
        'image_provider': os.getenv('IMAGE_PROVIDER', 'pollinations'),
        'proxy': os.getenv('PROXY_URL', None),
        'style_1': os.getenv('STYLE_IMG_1', 'cyberpunk'),
        'style_2': os.getenv('STYLE_IMG_2', 'sketch'),
        'style_remake': os.getenv('STYLE_REMAKE', 'realism'),
        'channel_signature': os.getenv('CHANNEL_SIGNATURE', '@CryptoNews'),
        'channel_url': os.getenv('CHANNEL_URL', None)
    }
