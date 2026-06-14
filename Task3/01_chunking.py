import json
import os
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(SCRIPT_DIR, "..", "Task2", "knowledge_base")
OUT_FILE = os.path.join(SCRIPT_DIR, "output", "chunks.jsonl")

# ============================================================
# Параметры чанкинга:
# - chunk_size  = 800 символов ≈ 500–1000 токенов (100–300 слов)
# - chunk_overlap = 150 символов — перекрытие для сохранения контекста
# - Минимальный размер чанка: 30 символов (фильтруем заголовки-одиночки)
# ============================================================
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_LENGTH = 30


def main() -> None:
    if not os.path.isdir(KB_PATH):
        print(f"❌  Папка {KB_PATH} не найдена. Сначала запустите Task2/02_replace.py")
        sys.exit(1)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    files = sorted(f for f in os.listdir(KB_PATH) if f.endswith(".txt"))
    print(f"📂  Найдено {len(files)} файлов в {KB_PATH}\n")

    # Создаём выходную папку
    out_dir = os.path.dirname(OUT_FILE)
    os.makedirs(out_dir, exist_ok=True)

    chunk_id_global = 0

    with open(OUT_FILE, "w", encoding="utf-8") as out_stream:
        for file in files:
            file_path = os.path.join(KB_PATH, file)
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            chunks = splitter.split_text(text)

            local_id = 0
            for chunk in chunks:
                # Пропускаем слишком короткие чанки (заголовки-одиночки)
                if len(chunk.strip()) < MIN_CHUNK_LENGTH:
                    continue

                # Находим позицию чанка в оригинальном тексте (char_offset)
                char_offset = text.find(chunk[:50])

                record = {
                    "id": chunk_id_global,
                    "text": chunk,
                    "metadata": {
                        "source": file,
                        "chunk_id": local_id,
                        "char_offset": char_offset if char_offset >= 0 else None,
                        "char_length": len(chunk),
                        "word_count": len(chunk.split()),
                    },
                }
                out_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_id_global += 1
                local_id += 1

            print(f"✅  {file}: {local_id} чанков")

    print(f"\n🏁  Чанкинг завершён. Создано чанков: {chunk_id_global}")
    print(f"📄  Файл сохранён: {OUT_FILE}\n")


if __name__ == "__main__":
    main()
