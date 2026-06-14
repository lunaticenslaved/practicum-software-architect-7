"""
Поиск по FAISS-индексу.

Принимает текстовый запрос, генерирует эмбеддинг через модель e5-large,
и ищет ближайшие документы в FAISS-индексе.

Использование:
    python Task3/04_search.py "Who is Toren Solwind?"
    python Task3/04_search.py "Tell me about the Great Convergence War"
    python Task3/04_search.py -k 10 "Verdania history"
"""

import argparse
import json
import os
import sys

import faiss
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

# ============================================================
# Конфигурация
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(SCRIPT_DIR, "faiss_index")
INDEX_FILE = os.path.join(INDEX_DIR, "index.faiss")
METADATA_FILE = os.path.join(INDEX_DIR, "metadata.json")

# Модель e5 требует префикс "query: " для поисковых запросов
MODEL_NAME = "intfloat/multilingual-e5-large"
QUERY_PREFIX = "query: "

# Количество результатов по умолчанию
DEFAULT_TOP_K = 5


def get_query_embedding(
    query: str,
    tokenizer: AutoTokenizer,
    model: AutoModel,
    device: str,
) -> np.ndarray:
    """
    Генерирует эмбеддинг для поискового запроса.
    Модель e5 требует префикс "query: " для запросов.
    """
    text = QUERY_PREFIX + query

    encoded = tokenizer(
        [text],
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**encoded)

    # Mean pooling
    last_hidden = outputs.last_hidden_state
    mask = encoded["attention_mask"].unsqueeze(-1).expand(last_hidden.size()).float()
    sum_embeddings = torch.sum(last_hidden * mask, dim=1)
    sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
    embedding = (sum_embeddings / sum_mask).squeeze(0)

    # L2-нормализация
    embedding = embedding / torch.clamp(torch.norm(embedding, p=2), min=1e-9)

    return embedding.cpu().numpy().astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Поиск по векторной базе знаний (FAISS)"
    )
    parser.add_argument("query", type=str, help="Текстовый поисковый запрос")
    parser.add_argument(
        "-k", "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Количество результатов (по умолчанию: {DEFAULT_TOP_K})",
    )
    args = parser.parse_args()

    # Проверяем наличие индекса
    if not os.path.isfile(INDEX_FILE):
        print(f"❌  Индекс {INDEX_FILE} не найден. Сначала запустите 03_index.py")
        sys.exit(1)

    if not os.path.isfile(METADATA_FILE):
        print(f"❌  Метаданные {METADATA_FILE} не найдены. Сначала запустите 03_index.py")
        sys.exit(1)

    # Загружаем FAISS-индекс
    print("🔄  Загрузка FAISS-индекса...")
    index = faiss.read_index(INDEX_FILE)
    print(f"✅  Индекс загружен: {index.ntotal} документов\n")

    # Загружаем метаданные
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata_store = json.load(f)

    # Загружаем модель для генерации эмбеддинга запроса
    print(f"🔄  Загрузка модели {MODEL_NAME}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()
    print("✅  Модель загружена!\n")

    # Генерируем эмбеддинг запроса
    query_embedding = get_query_embedding(args.query, tokenizer, model, device)

    # Поиск в FAISS (Inner Product = cosine similarity для нормализованных векторов)
    query_vector = query_embedding.reshape(1, -1)
    faiss.normalize_L2(query_vector)
    scores, indices = index.search(query_vector, args.top_k)

    # Выводим результаты
    print(f"🔍  Запрос: \"{args.query}\"")
    print(f"📊  Топ-{args.top_k} результатов:\n")

    for rank in range(len(indices[0])):
        idx = indices[0][rank]
        if idx == -1:
            continue

        similarity = scores[0][rank]
        doc_id = str(idx)
        entry = metadata_store.get(doc_id, {})
        text = entry.get("text", "N/A")
        metadata = entry.get("metadata", {})

        print(f"{'─' * 60}")
        print(f"  #{rank + 1}  |  ID: {doc_id}  |  Similarity: {similarity:.4f}")
        print(f"  Источник: {metadata.get('source', 'N/A')}")
        print(f"  Чанк: {metadata.get('chunk_id', 'N/A')}  |  Слов: {metadata.get('word_count', 'N/A')}")
        print(f"  Текст:")
        # Показываем первые 300 символов
        preview = text[:300] + ("..." if len(text) > 300 else "")
        print(f"  {preview}")
        print()

    print(f"{'─' * 60}")
    print(f"🏁  Найдено {min(args.top_k, index.ntotal)} результатов\n")


if __name__ == "__main__":
    main()
