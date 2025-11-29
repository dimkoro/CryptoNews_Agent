import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv
from datetime import datetime, timezone

# Загружаем конфиг
load_dotenv()
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')

channel_target = 'activitylauncher_offical' # Твой проблемный канал

async def main():
    print(f"--- ДИАГНОСТИКА КАНАЛА: {channel_target} ---")
    async with TelegramClient('anon_session', api_id, api_hash) as client:
        try:
            entity = await client.get_entity(channel_target)
            print(f"✅ Канал найден: {entity.title}")
            
            print("\n--- ПОСЛЕДНИЕ 5 СООБЩЕНИЙ ---")
            # Смотрим последние 5 постов
            async for msg in client.iter_messages(entity, limit=5):
                print(f"\n🆔 ID: {msg.id}")
                
                # 1. Проверка ВРЕМЕНИ
                msg_date = msg.date # Это всегда UTC
                now_utc = datetime.now(timezone.utc)
                age = (now_utc - msg_date).total_seconds() / 3600
                print(f"⏰ Дата (UTC): {msg_date}")
                print(f"⏳ Возраст: {age:.2f} часов (Лимит 4.0)")
                
                # 2. Проверка ТЕКСТА
                text_len = len(msg.text) if msg.text else 0
                print(f"📝 Длина текста: {text_len} символов (Лимит 50)")
                if msg.text:
                    print(f"📜 Текст (первые 50): {msg.text[:50]}...")
                else:
                    print("❌ Текста нет (только картинка/файл?)")

                # 3. ВЕРДИКТ
                is_fresh = age < 4.0
                is_long_enough = text_len > 50
                
                if not is_fresh:
                    print("RESULT: ⛔️ ОТКАЗ (Старый)")
                elif not is_long_enough:
                    print("RESULT: ⛔️ ОТКАЗ (Короткий)")
                else:
                    print("RESULT: ✅ ПРОХОДИТ!")

        except Exception as e:
            print(f"Ошибка: {e}")

    print("\n--- КОНЕЦ ДИАГНОСТИКИ ---")
    input("Нажми Enter чтобы выйти...")

if __name__ == '__main__':
    asyncio.run(main())