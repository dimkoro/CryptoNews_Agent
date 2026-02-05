import json
import os
import sys

# Имя файла, откуда берем инструкции
INPUT_FILE = 'blueprint.json'

def create_project():
    # Проверяем, есть ли файл с чертежом
    if not os.path.exists(INPUT_FILE):
        print(f"Ошибка: Файл {INPUT_FILE} не найден рядом со скриптом.")
        input("Нажмите Enter, чтобы выйти...")
        return

    try:
        # Читаем файл с кодировкой UTF-8 (для поддержки русского языка)
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        project_name = data.get('project_name', 'Untitled_Project')
        # Создаем проекты на уровень выше (в папке G:\Projects), а не внутри _Builder
        base_path = os.path.join('..', project_name) 
        
        print(f"--- Начинаю создание проекта: {project_name} ---")
        
        # Создаем главную папку проекта
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            print(f"[+] Создана папка: {project_name}")
        else:
            print(f"[!] Папка {project_name} уже существует. Файлы могут быть перезаписаны.")

        # Создаем файлы и папки из структуры
        files = data.get('structure', {})
        for filepath, content in files.items():
            # Полный путь к файлу
            full_path = os.path.join(base_path, filepath)
            
            # Если файл лежит в подпапке (например src/main.py), создаем подпапку
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Записываем контент в файл
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    -> Записан файл: {filepath}")

        print("\n" + "="*30)
        print("ГОТОВО! Проект успешно создан.")
        print("="*30)

    except json.JSONDecodeError:
        print("ОШИБКА: Неверный формат в blueprint.json. Проверьте, что вы скопировали код полностью.")
    except Exception as e:
        print(f"ОШИБКА: {e}")

    input("\nНажмите Enter, чтобы закрыть...")

if __name__ == '__main__':
    create_project()