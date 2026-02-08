import os
import sys
import aiosqlite
import asyncio
from dotenv import load_dotenv


REQUIRED_ENV = [
    'API_ID',
    'API_HASH',
    'BOT_TOKEN',
    'GEMINI_API_KEY',
    'PUB_CHANNEL_ID',
    'MOD_CHANNEL_ID'
]


def check_env():
    load_dotenv()
    missing = [key for key in REQUIRED_ENV if not os.getenv(key)]
    if missing:
        print(f"[FAIL] Missing in .env: {', '.join(missing)}")
        return False
    print("[OK] .env looks good.")
    return True


async def check_db():
    try:
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute("SELECT 1")
        print("[OK] Database доступна.")
        return True
    except Exception as e:
        print(f"[FAIL] Database ошибка: {e}")
        return False


def check_channels():
    if not os.path.exists('channels.txt'):
        print("[FAIL] channels.txt не найден.")
        return False
    with open('channels.txt', 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    if not lines:
        print("[FAIL] channels.txt пуст.")
        return False
    print(f"[OK] channels.txt: {len(lines)} канал(ов).")
    return True


def ensure_dirs():
    for d in ['media', 'temp']:
        os.makedirs(d, exist_ok=True)
    print("[OK] media/ и temp/ готовы.")
    return True


async def main():
    ok = True
    ok &= check_env()
    ok &= check_channels()
    ok &= ensure_dirs()
    ok &= await check_db()
    if not ok:
        print("Health-check: FAIL")
        sys.exit(1)
    print("Health-check: OK")


if __name__ == '__main__':
    asyncio.run(main())
