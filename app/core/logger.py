import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    logger = logging.getLogger('CryptoBot')
    logger.setLevel(logging.INFO)
    
    # Формат логов: Время - Уровень - Сообщение
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Вывод в файл (с ротацией, чтобы не забить диск)
    file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger