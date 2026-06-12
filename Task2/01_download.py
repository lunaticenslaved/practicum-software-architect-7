import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ============================================================
# Список страниц для скачивания — замените/дополните нужными.
# Имя должно совпадать с частью URL на вики (пробелы = _).
# Пример: "Kakashi_Hatake", "Naruto_Uzumaki", "Konohagakure"
# ============================================================

# --- 20 персонажей ---
CHARACTERS = [
    "Kakashi_Hatake",
    "Naruto_Uzumaki",
    "Sasuke_Uchiha",
    "Sakura_Haruno",
    "Itachi_Uchiha",
    "Hinata_Hyūga",
    "Gaara",
    "Jiraiya",
    "Tsunade",
    "Orochimaru",
    "Minato_Namikaze",
    "Obito_Uchiha",
    "Madara_Uchiha",
    "Shikamaru_Nara",
    "Rock_Lee",
    "Neji_Hyūga",
    "Might_Guy",
    "Killer_B",
    "Kabuto_Yakushi",
    "Nagato",
]

# --- 15 мест и событий ---
PLACES_AND_EVENTS = [
    "Konohagakure",
    "Sunagakure",
    "Kirigakure",
    "Kumogakure",
    "Iwagakure",
    "Amegakure",
    "Akatsuki",
    "Fourth_Shinobi_World_War",
    "Uchiha_Clan_Downfall",
    "Valley_of_the_End",
    "Mount_Myōboku",
    "Ryūchi_Cave",
    "Land_of_Fire",
]

PAGE_NAMES = CHARACTERS + PLACES_AND_EVENTS

# ============================================================
# Используем MediaWiki API вместо прямого доступа к страницам.
# Fandom защищён Cloudflare, который блокирует прямые HTTP-запросы
# (403 Forbidden). API-эндпоинт /api.php не проходит через
# Cloudflare и свободно отдаёт данные в формате JSON.
# ============================================================
API_URL = "https://naruto.fandom.com/api.php"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
DELAY_S = 1.5  # задержка между запросами, чтобы не нагружать сервер


def fetch_character_text(name: str) -> str:
    """
    Скачивает страницу через MediaWiki API (action=parse) и возвращает чистый текст.
    API не блокирует запросы, в отличие от прямого доступа к HTML-страницам.
    """
    page_name = name.replace("_", " ")
    params = {
        "action": "parse",
        "page": page_name,
        "prop": "text",
        "format": "json",
        "disablelimitreport": "true",
        "disableeditsection": "true",
    }

    print(f"⏳  Загрузка: {page_name}")

    response = requests.get(
        API_URL,
        params=params,
        headers={
            "User-Agent": "NarutoCharacterDownloader/1.0 (educational project)",
            "Accept": "application/json",
        },
    )
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(f"API ошибка: {data['error']['info']}")

    html = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")

    # Удаляем ненужные блоки: навигацию, инфобоксы, таблицы, скрипты, стили
    selectors_to_remove = [
        "script", "style", "noscript",
        ".navbox", ".infobox", ".portable-infobox",
        ".toc", ".mw-editsection", ".reference", ".references", ".reflist",
        "#References", ".navbox-container", ".messagebox", ".noprint",
        "table.wikitable", ".quote", ".mw-empty-elt", "sup.reference",
        ".thumb", "figure", "figcaption", ".gallery", ".wikia-gallery",
    ]
    for selector in selectors_to_remove:
        for element in soup.select(selector):
            element.decompose()

    # Извлекаем чистый текст
    text = soup.get_text()

    # Нормализуем пробелы и пустые строки
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


def main() -> None:
    """Главная функция: последовательно скачивает все страницы."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n🔰  Начинаем загрузку {len(PAGE_NAMES)} страниц...\n")

    success = 0
    failed = 0

    for name in PAGE_NAMES:
        try:
            text = fetch_character_text(name)

            filename = f"{name}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"✅  Сохранено: {filename} ({len(text)} символов)")
            success += 1
        except Exception as err:
            print(f"❌  Ошибка для {name}: {err}")
            failed += 1

        # Задержка между запросами
        time.sleep(DELAY_S)

    print(
        f"\n🏁  Готово! Успешно: {success}, ошибок: {failed}. "
        f"Файлы сохранены в {OUTPUT_DIR}\n"
    )


if __name__ == "__main__":
    main()
