"""
Загрузка эмбеддингов из embeddings.jsonl в FAISS-индекс.

Создаёт персистентный индекс в папке Task3/faiss_index/:
  - index.faiss  — FAISS-индекс (Inner Product / cosine для нормализованных векторов)
  - metadata.json — метаданные и тексты чанков (id → {text, metadata})
"""

import json
import os
import sys

import faiss
import numpy as np

# ============================================================
# Конфигурация
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDINGS_FILE = os.path.join(SCRIPT_DIR, "output", "embeddings.jsonl")
INDEX_DIR = os.path.join(SCRIPT_DIR, "faiss_index")
INDEX_FILE = os.path.join(INDEX_DIR, "index.faiss")
METADATA_FILE = os.path.join(INDEX_DIR, "metadata.json")


def main() -> None:
    if not os.path.isfile(EMBEDDINGS_FILE):
        print(f"❌  Файл {EMBEDDINGS_FILE} не найден. Сначала запустите 02_embeddings.py")
        sys.exit(1)

    # Загружаем эмбеддинги
    print(f"📂  Загрузка эмбеддингов из {EMBEDDINGS_FILE}...")
    with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    print(f"✅  Загружено {len(records)} записей\n")

    # Подготавливаем данные
    embeddings = np.array([r["embedding"] for r in records], dtype=np.float32)
    dimension = embeddings.shape[1]
    print(f"📊  Размерность эмбеддингов: {dimension}")
    print(f"📊  Матрица: {embeddings.shape}\n")

    # Создаём FAISS-индекс
    # Используем IndexFlatIP (Inner Product) — для L2-нормализованных векторов
    # Inner Product эквивалентен cosine similarity
    print("🔄  Создание FAISS-индекса (IndexFlatIP — cosine similarity)...")
    index = faiss.IndexFlatIP(dimension)

    # Нормализуем векторы (на случай если не были нормализованы)
    faiss.normalize_L2(embeddings)

    # Добавляем все эмбеддинги в индекс
    index.add(embeddings)
    print(f"✅  Добавлено {index.ntotal} векторов в индекс\n")

    # Сохраняем метаданные отдельно (FAISS не хранит метаданные)
    metadata_store = {}
    for r in records:
        metadata_store[str(r["id"])] = {
            "text": r["text"],
            "metadata": r["metadata"],
        }

    # Сохраняем на диск
    os.makedirs(INDEX_DIR, exist_ok=True)

    faiss.write_index(index, INDEX_FILE)
    print(f"💾  FAISS-индекс сохранён: {INDEX_FILE}")

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata_store, f, ensure_ascii=False, indent=2)
    print(f"💾  Метаданные сохранены: {METADATA_FILE}")

    print(f"\n🏁  Индексация завершена!")
    print(f"📊  Всего документов в индексе: {index.ntotal}")
    print(f"📁  Индекс сохранён в: {INDEX_DIR}\n")


if __name__ == "__main__":
    main()
