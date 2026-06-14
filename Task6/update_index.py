"""
Автоматическое инкрементальное обновление базы знаний и FAISS-индекса.

Источник данных: папка Task6/docs/ — симулирует внешний источник документов
(локальная папка, S3-бакет, Git-репозиторий и т.д.).

Алгоритм:
  1. Сканирует Task6/docs/ и сравнивает с манифестом (SHA-256 хеши)
  2. Копирует новые/изменённые файлы из docs/ → Task2/knowledge_base/
  3. Удаляет из knowledge_base файлы, удалённые из docs/
  4. Чанкирует только изменённые/новые файлы
  5. Генерирует эмбеддинги только для новых чанков
  6. Обновляет FAISS-индекс и метаданные
  7. Логирует весь процесс (консоль + файл)

Использование:
    python Task6/update_index.py              # инкрементальное обновление

Переменные окружения:
    DOCS_PATH — путь к папке-источнику (по умолчанию: Task6/docs)
"""

import hashlib
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime

import faiss
import numpy as np
import torch
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoModel, AutoTokenizer

# ============================================================
# Пути
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")

# Папка-источник (симулирует внешний источник данных)
DOCS_PATH = os.environ.get(
    "DOCS_PATH",
    os.path.join(SCRIPT_DIR, "docs"),
)

# Целевая папка базы знаний
KB_PATH = os.path.join(PROJECT_ROOT, "Task2", "knowledge_base")

# Выходные файлы (совместимы с Task3)
CHUNKS_FILE = os.path.join(PROJECT_ROOT, "Task3", "output", "chunks.jsonl")
EMBEDDINGS_FILE = os.path.join(PROJECT_ROOT, "Task3", "output", "embeddings.jsonl")
INDEX_DIR = os.path.join(PROJECT_ROOT, "Task3", "faiss_index")
INDEX_FILE = os.path.join(INDEX_DIR, "index.faiss")
METADATA_FILE = os.path.join(INDEX_DIR, "metadata.json")

# Манифест — хранит хеши файлов из docs/ с прошлого запуска
MANIFEST_FILE = os.path.join(SCRIPT_DIR, "manifest.json")

# Логи
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# ============================================================
# Параметры чанкинга (идентичны Task3/01_chunking.py)
# ============================================================
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
MIN_CHUNK_LENGTH = 30

# ============================================================
# Параметры эмбеддингов (идентичны Task3/02_embeddings.py)
# ============================================================
MODEL_NAME = "intfloat/multilingual-e5-large"
PASSAGE_PREFIX = "passage: "
BATCH_SIZE = 8


# ============================================================
# Логирование
# ============================================================
def setup_logging() -> logging.Logger:
    """Настраивает логирование в консоль и файл."""
    os.makedirs(LOG_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(LOG_DIR, f"update_{timestamp}.log")

    logger = logging.getLogger("kb_updater")
    logger.setLevel(logging.DEBUG)

    # Формат
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консоль (INFO+)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # Файл (DEBUG+)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    logger.info("Лог-файл: %s", log_file)
    return logger


# ============================================================
# Утилиты
# ============================================================
def sha256_file(filepath: str) -> str:
    """Вычисляет SHA-256 хеш файла."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest() -> dict:
    """Загружает манифест (хеши файлов docs/) с прошлого запуска."""
    if os.path.isfile(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manifest(manifest: dict) -> None:
    """Сохраняет манифест на диск."""
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def scan_docs(logger: logging.Logger) -> dict:
    """Сканирует папку-источник docs/ и возвращает {filename: sha256}."""
    if not os.path.isdir(DOCS_PATH):
        logger.error("Папка-источник не найдена: %s", DOCS_PATH)
        sys.exit(1)

    current = {}
    files = sorted(f for f in os.listdir(DOCS_PATH) if f.endswith(".txt"))
    for fname in files:
        fpath = os.path.join(DOCS_PATH, fname)
        current[fname] = sha256_file(fpath)

    logger.info("Сканирование docs/: найдено %d файлов в %s", len(current), DOCS_PATH)
    return current


def scan_kb(logger: logging.Logger) -> dict:
    """Сканирует текущую базу знаний и возвращает {filename: sha256}."""
    if not os.path.isdir(KB_PATH):
        logger.warning("Папка базы знаний не найдена: %s", KB_PATH)
        return {}

    current = {}
    files = sorted(f for f in os.listdir(KB_PATH) if f.endswith(".txt"))
    for fname in files:
        fpath = os.path.join(KB_PATH, fname)
        current[fname] = sha256_file(fpath)

    logger.info("Сканирование KB: найдено %d файлов в %s", len(current), KB_PATH)
    return current


def detect_changes(
    old_manifest: dict, current_docs: dict, logger: logging.Logger
) -> tuple:
    """
    Сравнивает манифест docs/ с текущим состоянием docs/.
    Возвращает (added, modified, deleted) — списки имён файлов.
    """
    old_files = set(old_manifest.keys())
    cur_files = set(current_docs.keys())

    added = sorted(cur_files - old_files)
    deleted = sorted(old_files - cur_files)
    modified = sorted(
        f
        for f in cur_files & old_files
        if current_docs[f] != old_manifest[f]
    )

    unchanged = len(cur_files & old_files) - len(modified)

    logger.info(
        "Изменения в docs/: +%d новых, ~%d изменённых, -%d удалённых, =%d без изменений",
        len(added), len(modified), len(deleted), unchanged,
    )

    for f in added:
        logger.debug("  + %s", f)
    for f in modified:
        logger.debug("  ~ %s", f)
    for f in deleted:
        logger.debug("  - %s", f)

    return added, modified, deleted


def sync_to_kb(
    added: list, modified: list, deleted: list, logger: logging.Logger
) -> None:
    """Синхронизирует docs/ → knowledge_base/: копирует новые/изменённые, удаляет удалённые."""
    os.makedirs(KB_PATH, exist_ok=True)

    for fname in added + modified:
        src = os.path.join(DOCS_PATH, fname)
        dst = os.path.join(KB_PATH, fname)
        shutil.copy2(src, dst)
        action = "Добавлен" if fname in added else "Обновлён"
        logger.info("  %s → KB: %s", action, fname)

    for fname in deleted:
        dst = os.path.join(KB_PATH, fname)
        if os.path.isfile(dst):
            os.remove(dst)
            logger.info("  Удалён из KB: %s", fname)


# ============================================================
# Чанкинг
# ============================================================
def chunk_files(filenames: list, logger: logging.Logger) -> list:
    """
    Чанкирует указанные файлы из knowledge_base/.
    Возвращает список записей [{text, metadata}].
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    all_chunks = []
    for fname in filenames:
        fpath = os.path.join(KB_PATH, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()

        raw_chunks = splitter.split_text(text)
        local_id = 0
        for chunk in raw_chunks:
            if len(chunk.strip()) < MIN_CHUNK_LENGTH:
                continue
            char_offset = text.find(chunk[:50])
            record = {
                "text": chunk,
                "metadata": {
                    "source": fname,
                    "chunk_id": local_id,
                    "char_offset": char_offset if char_offset >= 0 else None,
                    "char_length": len(chunk),
                    "word_count": len(chunk.split()),
                },
            }
            all_chunks.append(record)
            local_id += 1

        logger.debug("  Чанкинг %s: %d чанков", fname, local_id)

    logger.info("Чанкинг завершён: %d чанков из %d файлов", len(all_chunks), len(filenames))
    return all_chunks


# ============================================================
# Эмбеддинги
# ============================================================
def mean_pooling(
    last_hidden_state: torch.Tensor,
    attention_mask: torch.Tensor,
) -> np.ndarray:
    """Mean pooling + L2-нормализация."""
    mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    sum_embeddings = torch.sum(last_hidden_state * mask_expanded, dim=1)
    sum_mask = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
    embeddings = sum_embeddings / sum_mask

    norms = torch.norm(embeddings, p=2, dim=1, keepdim=True)
    norms = torch.clamp(norms, min=1e-9)
    embeddings = embeddings / norms

    return embeddings.detach().cpu().numpy()


def generate_embeddings(
    chunks: list, logger: logging.Logger
) -> list:
    """
    Генерирует эмбеддинги для списка чанков.
    Возвращает список np.ndarray (по одному вектору на чанк).
    """
    if not chunks:
        return []

    logger.info("Загрузка модели %s...", MODEL_NAME)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()
    logger.info("Модель загружена (device=%s)", device)

    all_embeddings = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [PASSAGE_PREFIX + c["text"] for c in batch]

        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            outputs = model(**encoded)

        embs = mean_pooling(outputs.last_hidden_state, encoded["attention_mask"])
        all_embeddings.extend(embs)

        processed = min(i + BATCH_SIZE, len(chunks))
        if processed % 100 == 0 or processed == len(chunks):
            logger.info(
                "Эмбеддинги: %d/%d (%.1f%%)",
                processed, len(chunks), processed / len(chunks) * 100,
            )

    logger.info("Генерация эмбеддингов завершена: %d векторов", len(all_embeddings))
    return all_embeddings


# ============================================================
# Индекс
# ============================================================
def load_existing_data(logger: logging.Logger) -> list:
    """Загружает существующие записи из embeddings.jsonl."""
    records = []
    if os.path.isfile(EMBEDDINGS_FILE):
        with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        logger.info("Загружено %d существующих записей из embeddings.jsonl", len(records))
    else:
        logger.info("Файл embeddings.jsonl не найден — начинаем с нуля")

    return records


def rebuild_index(records: list, logger: logging.Logger) -> None:
    """Пересобирает FAISS-индекс и метаданные из полного списка записей."""
    if not records:
        logger.warning("Нет записей для индексации!")
        return

    embeddings = np.array([r["embedding"] for r in records], dtype=np.float32)
    dimension = embeddings.shape[1]

    # Нормализация
    faiss.normalize_L2(embeddings)

    # Создаём индекс
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    # Метаданные
    metadata_store = {}
    for r in records:
        metadata_store[str(r["id"])] = {
            "text": r["text"],
            "metadata": r["metadata"],
        }

    # Сохраняем
    os.makedirs(INDEX_DIR, exist_ok=True)
    faiss.write_index(index, INDEX_FILE)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata_store, f, ensure_ascii=False, indent=2)

    logger.info(
        "FAISS-индекс пересобран: %d векторов, размерность %d",
        index.ntotal, dimension,
    )


def save_intermediate_files(records: list, logger: logging.Logger) -> None:
    """Сохраняет обновлённые chunks.jsonl и embeddings.jsonl."""
    os.makedirs(os.path.dirname(CHUNKS_FILE), exist_ok=True)

    # chunks.jsonl
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for r in records:
            chunk_record = {
                "id": r["id"],
                "text": r["text"],
                "metadata": r["metadata"],
            }
            f.write(json.dumps(chunk_record, ensure_ascii=False) + "\n")
    logger.debug("Сохранён %s (%d записей)", CHUNKS_FILE, len(records))

    # embeddings.jsonl
    with open(EMBEDDINGS_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.debug("Сохранён %s (%d записей)", EMBEDDINGS_FILE, len(records))


# ============================================================
# Основная логика обновления
# ============================================================
def incremental_update(
    added: list,
    modified: list,
    deleted: list,
    logger: logging.Logger,
) -> None:
    """Выполняет инкрементальное обновление индекса."""
    # 1. Синхронизируем docs/ → knowledge_base/
    logger.info("Синхронизация docs/ → knowledge_base/...")
    sync_to_kb(added, modified, deleted, logger)

    # 2. Загружаем существующие данные
    existing_records = load_existing_data(logger)

    # 3. Определяем файлы, чанки которых нужно удалить
    files_to_remove = set(modified + deleted)
    files_to_add = added + modified

    # 4. Удаляем чанки удалённых/изменённых файлов
    if files_to_remove:
        before = len(existing_records)
        existing_records = [
            r for r in existing_records
            if r["metadata"]["source"] not in files_to_remove
        ]
        removed_count = before - len(existing_records)
        logger.info(
            "Удалено %d устаревших чанков из %d файлов",
            removed_count, len(files_to_remove),
        )

    # 5. Чанкируем новые/изменённые файлы
    new_chunks = []
    if files_to_add:
        new_chunks = chunk_files(files_to_add, logger)

    # 6. Генерируем эмбеддинги для новых чанков
    new_embeddings = []
    if new_chunks:
        new_embeddings = generate_embeddings(new_chunks, logger)

    # 7. Определяем следующий ID
    max_id = max((r["id"] for r in existing_records), default=-1)
    next_id = max_id + 1

    # 8. Формируем новые записи
    new_records = []
    for i, chunk in enumerate(new_chunks):
        record = {
            "id": next_id + i,
            "embedding": new_embeddings[i].tolist(),
            "metadata": chunk["metadata"],
            "text": chunk["text"],
        }
        new_records.append(record)

    logger.info("Добавлено %d новых чанков", len(new_records))

    # 9. Объединяем и перенумеровываем
    all_records = existing_records + new_records
    for i, r in enumerate(all_records):
        r["id"] = i

    # 10. Сохраняем
    save_intermediate_files(all_records, logger)
    rebuild_index(all_records, logger)

    logger.info("Итого в индексе: %d чанков", len(all_records))


# ============================================================
# Структурированное резюме
# ============================================================
def write_summary(
    logger: logging.Logger,
    start_time: float,
    status: str,
    new_chunks: int = 0,
    removed_chunks: int = 0,
    total_index_size: int = 0,
    files_added: int = 0,
    files_modified: int = 0,
    files_deleted: int = 0,
    error: str = None,
) -> None:
    """Записывает структурированное JSON-резюме в лог и отдельный файл."""
    elapsed = time.time() - start_time
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "duration_sec": round(elapsed, 1),
        "files": {
            "added": files_added,
            "modified": files_modified,
            "deleted": files_deleted,
        },
        "chunks": {
            "new": new_chunks,
            "removed": removed_chunks,
            "total_index_size": total_index_size,
        },
        "error": error,
    }

    # Записываем в лог
    logger.info("=" * 60)
    logger.info("РЕЗЮМЕ ОБНОВЛЕНИЯ")
    logger.info("=" * 60)
    logger.info("Статус:            %s", status)
    logger.info("Время выполнения:  %.1f сек", elapsed)
    logger.info("Файлов добавлено:  %d", files_added)
    logger.info("Файлов изменено:   %d", files_modified)
    logger.info("Файлов удалено:    %d", files_deleted)
    logger.info("Новых чанков:      %d", new_chunks)
    logger.info("Удалённых чанков:  %d", removed_chunks)
    logger.info("Размер индекса:    %d", total_index_size)
    if error:
        logger.error("Ошибка:            %s", error)
    logger.info("=" * 60)

    # Записываем JSON-резюме в отдельный файл
    summary_file = os.path.join(LOG_DIR, "last_update_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.debug("JSON-резюме сохранено: %s", summary_file)


# ============================================================
# Точка входа
# ============================================================
def main() -> int:
    """Возвращает код выхода: 0 — успех, 1 — ошибка."""
    start_time = time.time()
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Обновление базы знаний — старт")
    logger.info("=" * 60)
    logger.info("Источник (docs/): %s", DOCS_PATH)
    logger.info("База знаний (KB): %s", KB_PATH)

    # Счётчики для резюме
    stats = {
        "new_chunks": 0,
        "removed_chunks": 0,
        "total_index_size": 0,
        "files_added": 0,
        "files_modified": 0,
        "files_deleted": 0,
    }

    try:
        old_manifest = load_manifest()
        current_docs = scan_docs(logger)

        if not old_manifest:
            # Манифест не найден — все файлы docs/ считаются новыми
            logger.info(
                "Манифест не найден — все %d файлов docs/ считаются новыми",
                len(current_docs),
            )
            added = sorted(current_docs.keys())
            modified = []
            deleted = []
        else:
            added, modified, deleted = detect_changes(
                old_manifest, current_docs, logger
            )

        stats["files_added"] = len(added)
        stats["files_modified"] = len(modified)
        stats["files_deleted"] = len(deleted)

        if not added and not modified and not deleted:
            logger.info("Изменений в docs/ не обнаружено — индекс актуален")
            if os.path.isfile(EMBEDDINGS_FILE):
                with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                    stats["total_index_size"] = sum(1 for _ in f)
        else:
            incremental_update(added, modified, deleted, logger)
            save_manifest(current_docs)
            logger.info(
                "Манифест обновлён (%d файлов из docs/)", len(current_docs)
            )
            # Подсчитываем итоговый размер индекса
            if os.path.isfile(EMBEDDINGS_FILE):
                with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
                    stats["total_index_size"] = sum(1 for _ in f)

        write_summary(logger, start_time, status="OK", **stats)
        return 0

    except Exception as e:
        logger.exception("Критическая ошибка: %s", e)
        write_summary(logger, start_time, status="ERROR", error=str(e), **stats)
        return 1


if __name__ == "__main__":
    sys.exit(main())
