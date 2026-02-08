import asyncio
import sys
from datetime import datetime, timezone, timedelta
from app.core.logger import setup_logger
from app.core.config import load_config
from app.core.database import Database
from app.services.telegram_service import TelegramSpy
from app.services.ai_service import AIService
from app.services.image_service import ImageService
from app.services.bot_service import BotManager
from app.services.runtime_service import (
    disable_quickedit,
    scheduler,
    production,
    STATE
)

VERSION = "v17.4 (Stable)"

logger = setup_logger()


async def main_loop():
    disable_quickedit()
    logger.info(f'--- CRYPTONEWS AGENT {VERSION} ---')
    config = load_config()
    db = Database()
    await db.init_db()
    spy = TelegramSpy(config)
    await spy.start_spy()
    ai = AIService(config['gemini_key'], config['proxy'])
    img = ImageService(
        provider=config['image_provider'],
        api_key=config['unsplash_key'],
        hf_key=config['hf_key'],
        proxy=config['proxy'],
        hf_model=config['hf_model'],
        hf_width=config['hf_width'],
        hf_height=config['hf_height'],
        fallback_list=config['image_fallbacks'],
        pollinations_base_url=config['pollinations_base_url'],
        pollinations_model=config['pollinations_model'],
        pollinations_width=config['pollinations_width'],
        pollinations_height=config['pollinations_height'],
        pollinations_retries=config['pollinations_retries'],
        pollinations_timeout=config['pollinations_timeout']
    )
    bot = BotManager(config, db, spy.client, ai, img)
    await bot.start()

    saved = await db.get_state()
    if saved:
        try:
            st = datetime.fromisoformat(saved['cycle_start_time'])
            # Если сохраненный цикл свежее 4 часов - восстанавливаем
            if (datetime.now(timezone.utc) - st).total_seconds() < 4 * 3600:
                STATE.start_time = st
                STATE.published = saved['published_count']
                STATE.attempts = saved['attempts_count']
                STATE.is_resumed = True
                logger.info(
                    f"📂 Восстановлено состояние: {STATE.published}/3 pubs, {STATE.attempts} attempts"
                )
        except Exception:
            pass

    def norm(l):
        return l.replace('https://', '').replace('t.me/', '').strip('/')

    try:
        with open('channels.txt', 'r') as f:
            ch = [norm(l.strip()) for l in f if l.strip()]
    except Exception:
        ch = []

    asyncio.create_task(scheduler(spy, db, ai, ch))
    await production(db, ai, img, spy, bot, config)


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка.")
    except Exception as e:
        logger.critical(f"🔥 {e}")
