import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
if os.getenv('PROXY_URL'):
    os.environ['http_proxy'] = os.getenv('PROXY_URL')
    os.environ['https_proxy'] = os.getenv('PROXY_URL')

# Проверяем именно живой алиас из твоего лога
model_name = 'models/gemini-flash-latest'
print(f"--- ТЕСТ АЛИАСА ({model_name}) ---")
try:
    model = genai.GenerativeModel(model_name)
    res = model.generate_content("Привет! Ты работаешь?")
    print(f"✅ УСПЕХ! Ответ: {res.text[:15]}")
except Exception as e:
    print(f"❌ ОШИБКА: {e}")