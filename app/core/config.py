import os
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    config = {
        'api_id': os.getenv('API_ID'),
        'api_hash': os.getenv('API_HASH'),
        'bot_token': os.getenv('BOT_TOKEN'),
        'phone': os.getenv('PHONE'),
        'admin_id': int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else None,
        'mod_channel': os.getenv('MOD_CHANNEL_ID'),
        'pub_channel': os.getenv('PUB_CHANNEL_ID'),
        'gemini_key': os.getenv('GEMINI_API_KEY'),
        'unsplash_key': os.getenv('UNSPLASH_ACCESS_KEY'),
        'proxy': os.getenv('PROXY_URL')
    }
    # Проверка критических ключей
    required = ['api_id', 'api_hash', 'bot_token', 'gemini_key']
    missing = [k for k in required if not config[k] or 'твои' in str(config[k])]
    if missing:
        raise ValueError(f'Не заполнены ключи в .env: {missing}')
    return config