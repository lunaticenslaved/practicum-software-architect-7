import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "raw")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "knowledge_base")
TERMS_MAP_PATH = os.path.join(SCRIPT_DIR, "terms_map.json")


def build_replacement_map() -> tuple[dict[str, str], list[str]]:
    """
    Загружает terms_map.json и строит плоский словарь замен { original → replacement }.
    Сортирует ключи по длине (от длинных к коротким), чтобы длинные фразы
    заменялись раньше коротких и не ломали друг друга.
    """
    with open(TERMS_MAP_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Объединяем все категории в один плоский словарь
    flat: dict[str, str] = {}
    for category in raw.values():
        for original, replacement in category.items():
            flat[original] = replacement

    # Сортируем ключи по убыванию длины — длинные фразы заменяются первыми
    sorted_keys = sorted(flat.keys(), key=len, reverse=True)

    return flat, sorted_keys


def apply_replacements(text: str, flat: dict[str, str], sorted_keys: list[str]) -> str:
    """
    Применяет все замены к тексту.
    Использует регулярные выражения для точного совпадения.
    """
    result = text

    for key in sorted_keys:
        # Экранируем спецсимволы regex в ключе
        escaped = re.escape(key)
        result = re.sub(escaped, flat[key], result)

    return result


def replace_filename(filename: str, flat: dict[str, str], sorted_keys: list[str]) -> str:
    """Определяет новое имя файла, заменяя термины в имени файла."""
    # Убираем расширение
    name = filename.removesuffix(".txt")

    # Заменяем подчёркивания на пробелы для поиска совпадений
    readable = name.replace("_", " ")

    # Применяем замены к читаемому имени
    for key in sorted_keys:
        escaped = re.escape(key)
        readable = re.sub(escaped, flat[key], readable)

    # Возвращаем подчёркивания и расширение
    return readable.replace(" ", "_") + ".txt"


def main() -> None:
    """Главная функция."""
    # Проверяем наличие исходных данных
    if not os.path.isdir(RAW_DIR):
        print(f"❌  Папка {RAW_DIR} не найдена. Сначала запустите 01_download.py")
        sys.exit(1)

    if not os.path.isfile(TERMS_MAP_PATH):
        print(f"❌  Файл {TERMS_MAP_PATH} не найден.")
        sys.exit(1)

    # Создаём выходную папку
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Строим словарь замен
    flat, sorted_keys = build_replacement_map()
    print(f"📖  Загружено {len(sorted_keys)} терминов для замены.\n")

    # Получаем список файлов
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".txt"))
    print(f"📂  Найдено {len(files)} файлов в {RAW_DIR}\n")

    processed = 0

    for file in files:
        input_path = os.path.join(RAW_DIR, file)
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Заменяем термины в тексте
        replaced_text = apply_replacements(text, flat, sorted_keys)

        # Заменяем термины в имени файла
        new_filename = replace_filename(file, flat, sorted_keys)
        output_path = os.path.join(OUTPUT_DIR, new_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(replaced_text)

        print(f"✅  {file} → {new_filename}")
        processed += 1

    print(
        f"\n🏁  Готово! Обработано файлов: {processed}. "
        f"Результат в {OUTPUT_DIR}\n"
    )


if __name__ == "__main__":
    main()
