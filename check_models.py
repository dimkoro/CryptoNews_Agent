import google.generativeai as genai
import os
from dotenv import load_dotenv

# Загружаем настройки
load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
proxy = os.getenv('PROXY_URL')

print("--- ДИАГНОСТИКА AI ---")

if not api_key:
    print("❌ ОШИБКА: Нет ключа GEMINI_API_KEY в .env")
    exit()
else:
    print(f"🔑 Ключ найден: {api_key[:5]}...***")

if proxy:
    os.environ['http_proxy'] = proxy
    os.environ['https_proxy'] = proxy
    print(f"🌍 Прокси установлен: {proxy}")
else:
    print("⚠️ Прокси НЕ задан (в РФ работать не будет)")

try:
    genai.configure(api_key=api_key)
    print("\n🔄 Стучимся в Google API...")
    
    # Запрашиваем список моделей
    models = genai.list_models()
    
    print("\n✅ ДОСТУПНЫЕ МОДЕЛИ (для генерации текста):")
    count = 0
    for m in models:
        if 'generateContent' in m.supported_generation_methods:
            print(f" • {m.name}")
            count += 1
            
    if count == 0:
        print("⚠️ Соединение есть, но моделей для текста не найдено.")
    else:
        print(f"\nВсего найдено: {count}")

except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
    print("Совет: Проверь VPN/Прокси или смени API ключ.")
    
input("\nНажми Enter чтобы выйти...")