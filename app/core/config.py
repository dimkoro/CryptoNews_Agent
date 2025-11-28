import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger('CryptoBot')

def load_config():
    load_dotenv()
    
    config = {}
    # Добавляем HUGGINGFACE_KEY в обязательные (или опциональные, если хотим переключаться)
    config['api_id'] = os.getenv('API_ID')
    config['api_hash'] = os.getenv('API_HASH')
    config['bot_token'] = os.getenv('BOT_TOKEN')
    config['phone'] = os.getenv('PHONE')
    config['gemini_key'] = os.getenv('GEMINI_API_KEY')
    config['mod_channel'] = os.getenv('MOD_CHANNEL_ID')
    config['pub_channel'] = os.getenv('PUB_CHANNEL_ID')
    config['proxy'] = os.getenv('PROXY_URL')
    config['admin_id'] = os.getenv('ADMIN_ID')
    
    # Настройки картинок
    config['unsplash_key'] = os.getenv('UNSPLASH_ACCESS_KEY')
    config['hf_key'] = os.getenv('HUGGINGFACE_KEY') # НОВАЯ ПЕРЕМЕННАЯ
    config['image_provider'] = os.getenv('IMAGE_PROVIDER', 'ai').lower()

    # Проверка только критических для запуска Telegram ключей
    required = ['api_id', 'api_hash', 'bot_token']
    missing = [k for k in required if not config[k]]
    if missing:
        raise ValueError(f"Нет ключей: {missing}")
        
    # Преобразование ID
    try:
        if config['mod_channel']: config['mod_channel'] = int(config['mod_channel'])
        if config['pub_channel']: config['pub_channel'] = int(config['pub_channel'])
        if config['admin_id']: config['admin_id'] = int(config['admin_id'])
    except: pass
    
    return config