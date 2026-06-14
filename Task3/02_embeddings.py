import json
import os
import sys

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

# ============================================================
# Конфигурация
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHUNKS_FILE = os.path.join(SCRIPT_DIR, "output", "chunks.jsonl")
OUT_FILE = os.path.join(SCRIPT_DIR, "output", "embeddings.jsonl")

# Модель: intfloat/multilingual-e5-large
# Требует префикс "passage: " для индексируемых документов
MODEL_NAME = "intfloat/multilingual-e5-large"
PASSAGE_PREFIX = "passage: "

# Размер батча — сколько чанков обрабатывать за раз
BATCH_SIZE = 8


def mean_pooling(
    last_hidden_state: torch.Tensor,
    attention_mask: torch.Tensor,
) -> np.ndarray:
    """
    Средний пулинг (mean pooling) — усредняет токен-эмбеддинги
    с учётом attention mask, затем L2-нормализует.
    """
    # Расширяем маску до размерности hidden state
    mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()

    # Суммируем только замаскированные токены
    sum_embeddings = torch.sum(last_hidden_state * mask_expanded, dim=1)
    sum_mask = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
    embeddings = sum_embeddings / sum_mask

    # L2-нормализация
    norms = torch.norm(embeddings, p=2, dim=1, keepdim=True)
    norms = torch.clamp(norms, min=1e-9)
    embeddings = embeddings / norms

    return embeddings.detach().cpu().numpy()


def main() -> None:
    if not os.path.isfile(CHUNKS_FILE):
        print(f"❌  Файл {CHUNKS_FILE} не найден. Сначала запустите 01_chunking.py")
        sys.exit(1)

    # Загружаем чанки
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    print(f"📂  Загружено {len(chunks)} чанков из {CHUNKS_FILE}\n")

    # Загружаем модель
    print(f"🔄  Загрузка модели {MODEL_NAME}...")
    print("    (первый запуск скачает ~2.2 ГБ модели)\n")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    print("✅  Модель загружена!\n")

    # Создаём выходную папку
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)

    # Генерируем эмбеддинги батчами
    processed = 0

    with open(OUT_FILE, "w", encoding="utf-8") as out_stream:
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]

            # Добавляем префикс "passage: " как требует модель e5
            texts = [PASSAGE_PREFIX + c["text"] for c in batch]

            # Токенизация
            encoded = tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(device)

            # Получаем эмбеддинги
            with torch.no_grad():
                outputs = model(**encoded)

            embeddings = mean_pooling(outputs.last_hidden_state, encoded["attention_mask"])

            # Записываем результаты
            for j, chunk in enumerate(batch):
                record = {
                    "id": chunk["id"],
                    "embedding": embeddings[j].tolist(),
                    "metadata": chunk["metadata"],
                    "text": chunk["text"],
                }
                out_stream.write(json.dumps(record, ensure_ascii=False) + "\n")

            processed += len(batch)

            if processed % 100 == 0 or processed == len(chunks):
                pct = processed / len(chunks) * 100
                print(f"⏳  Обработано: {processed}/{len(chunks)} ({pct:.1f}%)")

    print(f"\n🏁  Генерация эмбеддингов завершена!")
    print(f"📄  Файл сохранён: {OUT_FILE}")
    print(f"📊  Всего записей: {processed}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"❌  Ошибка: {err}")
        sys.exit(1)
