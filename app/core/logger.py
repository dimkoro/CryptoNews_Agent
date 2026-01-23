import logging
import sys

def setup_logger():
    logger = logging.getLogger('CryptoBot')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    fh = logging.FileHandler('bot.log', encoding='utf-8')
    fh.setFormatter(formatter)
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
