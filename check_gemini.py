import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Загружаем переменные из .env
# Скрипт будет искать файл .env в текущей папке
load_dotenv()

# 2. Получаем ключ по названию из твоего файла
API_KEY = os.getenv("GEMINI_API_KEY")

# Проверка: если ключа нет или он пустой
if not API_KEY:
    print("❌ ОШИБКА: Переменная GEMINI_API_KEY не найдена или пуста.")
    print("Убедитесь, что у вас есть файл .env и в нем прописан ключ:")
    print("GEMINI_API_KEY=AIzaSy...")
    exit()

def get_model_estimates(model_name):
    name = model_name.lower()
    if "gemini-2.0" in name or "exp" in name:
        return {"rpm": "10", "rpd": "1500", "price": "Бесплатно (Preview)"}
    elif "flash-lite" in name:
        return {"rpm": "15", "rpd": "1500", "price": "$0.075 / 1M"}
    elif "flash" in name:
        return {"rpm": "15", "rpd": "1500", "price": "$0.075 / 1M"}
    elif "pro" in name:
        return {"rpm": "2",  "rpd": "50",   "price": "$3.50 / 1M"}
    else:
        return {"rpm": "?",  "rpd": "?",    "price": "?"}

def check_status(client, model_name):
    try:
        # Отправляем 1 токен для проверки жизни модели
        response = client.models.generate_content(
            model=model_name,
            contents="Hi",
            config=types.GenerateContentConfig(max_output_tokens=1)
        )
        if response and response.text:
            return "✅ OK"
        return "⚠️ Пустой ответ"
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            return "⛔ Лимит (429)"
        elif "404" in error_msg:
            return "❌ Не найдена"
        elif "User location" in error_msg:
            return "🌍 Блок региона"
        else:
            return "❌ Ошибка"

def main():
    print(f"\n🔑 Ключ успешно загружен (переменная GEMINI_API_KEY)")
    
    try:
        # Инициализация клиента с ключом из файла
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        return
    
    print(f"Запуск диагностики... Пожалуйста, подождите.\n")
    print(f"{'МОДЕЛЬ':<35} | {'СТАТУС':<12} | {'КОНТЕКСТ':<10} | {'RPM (Free)':<10} | {'ЦЕНА (Paid)'}")
    print("-" * 100)

    try:
        all_models = client.models.list()
        found_any = False
        
        for m in all_models:
            if "generateContent" in (m.supported_actions or []) and "gemini" in m.name:
                found_any = True
                clean_name = m.name.replace("models/", "")
                
                status = check_status(client, clean_name)
                
                limit = m.input_token_limit if hasattr(m, 'input_token_limit') else 0
                context = f"{int(limit/1000)}K"
                
                est = get_model_estimates(clean_name)
                
                print(f"{clean_name:<35} | {status:<12} | {context:<10} | {est['rpm']:<10} | {est['price']}")
                time.sleep(1) # Пауза, чтобы не словить бан

        if not found_any:
            print("\nНе найдено моделей. Возможно, ключ некорректен.")

    except Exception as e:
        print(f"\nКритическая ошибка: {e}")

if __name__ == "__main__":
    main()