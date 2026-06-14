"""
Запуск золотого набора тестовых запросов (golden set).

Двухфазный прогон:
  Фаза 1 — удаляет сущности из БЗ, пересобирает индекс, запускает absent-запросы.
  Фаза 2 — восстанавливает сущности, пересобирает индекс, запускает known-запросы.

Файлы сущностей гарантированно восстанавливаются даже при ошибке (try/finally).

Использование:
    python Task7/evaluate.py
"""

import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Task4")
)

from rag_engine import RAGEngine  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
GOLDEN_SET_FILE = os.path.join(SCRIPT_DIR, "golden_questions.json")
RESULTS_FILE = os.path.join(SCRIPT_DIR, "golden_questions_results.json")

KB_DIR = os.path.join(PROJECT_ROOT, "Task2", "knowledge_base")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backup")

PYTHON = sys.executable

# Скрипты пересборки индекса (Task3)
CHUNKING_SCRIPT = os.path.join(PROJECT_ROOT, "Task3", "01_chunking.py")
EMBEDDINGS_SCRIPT = os.path.join(PROJECT_ROOT, "Task3", "02_embeddings.py")
INDEX_SCRIPT = os.path.join(PROJECT_ROOT, "Task3", "03_index.py")


def separator(title):
    print("\n" + "=" * 70)
    print("  " + title)
    print("=" * 70)


def evaluate_answer(answer, expected_keywords):
    answer_lower = answer.lower()

    refusal_markers = [
        "не нашёл", "не найден", "не знаю", "нет информации",
        "no information", "cannot answer", "don't have",
        "not found", "no relevant", "недостаточно информации",
        "не удалось найти", "не могу ответить",
    ]
    is_refusal = any(m in answer_lower for m in refusal_markers)
    is_error = answer.startswith("❌")

    hits = []
    misses = []
    for kw in expected_keywords:
        if kw.lower() in answer_lower:
            hits.append(kw)
        else:
            misses.append(kw)

    total = len(expected_keywords) if expected_keywords else 1
    coverage = round(len(hits) / total, 3)

    return {
        "keyword_hits": hits,
        "keyword_misses": misses,
        "coverage": coverage,
        "is_refusal": is_refusal,
        "is_error": is_error,
        "answer_length": len(answer),
    }


def rebuild_index():
    """Пересобирает чанки, эмбеддинги и FAISS-индекс (Task3 pipeline)."""
    for script, label in [
        (CHUNKING_SCRIPT, "Chunking"),
        (EMBEDDINGS_SCRIPT, "Embeddings"),
        (INDEX_SCRIPT, "FAISS index"),
    ]:
        print("  🔄 " + label + "...")
        result = subprocess.run(
            [PYTHON, script],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("  ❌ " + label + " failed:")
            print(result.stderr)
            sys.exit(1)
    print("  ✅ Индекс пересобран")


def remove_entities(entity_files):
    """Перемещает файлы сущностей из БЗ в backup/."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    removed = []
    for fname in entity_files:
        src = os.path.join(KB_DIR, fname)
        dst = os.path.join(BACKUP_DIR, fname)
        if os.path.isfile(src):
            shutil.move(src, dst)
            removed.append(fname)
            print("  🗑️  Удалён: " + fname)
        else:
            print("  ⚠️  Не найден: " + fname)
    return removed


def restore_entities(entity_files):
    """Восстанавливает файлы сущностей из backup/ в БЗ."""
    restored = []
    for fname in entity_files:
        src = os.path.join(BACKUP_DIR, fname)
        dst = os.path.join(KB_DIR, fname)
        if os.path.isfile(src):
            shutil.move(src, dst)
            restored.append(fname)
            print("  ♻️  Восстановлен: " + fname)
        else:
            print("  ⚠️  Не найден в backup: " + fname)
    # Удаляем пустую папку backup
    if os.path.isdir(BACKUP_DIR) and not os.listdir(BACKUP_DIR):
        os.rmdir(BACKUP_DIR)
    return restored


def run_queries(rag, queries, results, known_stats, absent_stats):
    """Прогоняет список запросов через RAG и собирает результаты."""
    for q in queries:
        group_label = "Known" if q["group"] == "known" else "Absent"
        separator("[" + q["id"] + "] " + group_label + ": " + q["description"])
        print("❓ " + q["query"])
        print("⏳ Обработка...")

        start = time.time()
        try:
            rag_result = rag.ask(q["query"])
            elapsed = round(time.time() - start, 2)
            answer = rag_result["answer"]
            chunks = rag_result["chunks"]
            sources = rag_result["sources"]

            evaluation = evaluate_answer(answer, q["expected_keywords"])

            # Определяем, прошёл ли тест
            if q["group"] == "known":
                known_stats["total"] += 1
                test_pass = (
                    evaluation["coverage"] >= 0.5
                    and not evaluation["is_refusal"]
                )
                if test_pass:
                    known_stats["pass"] += 1
            else:
                absent_stats["total"] += 1
                # Для absent-запросов: тест проходит, если coverage < 0.8
                # или есть refusal
                test_pass = (
                    evaluation["coverage"] < 0.8
                    or evaluation["is_refusal"]
                )
                if test_pass:
                    absent_stats["pass"] += 1

            status = "✅ PASS" if test_pass else "❌ FAIL"
            cov_pct = "{:.0%}".format(evaluation["coverage"])

            print("\n💬 Ответ (первые 300 символов):")
            print(answer[:300] + ("..." if len(answer) > 300 else ""))
            print(
                "\n📊 Coverage: " + cov_pct
                + " | Refusal: " + str(evaluation["is_refusal"])
                + " | Chunks: " + str(len(chunks))
                + " | Time: " + str(elapsed) + "s"
            )
            if evaluation["keyword_hits"]:
                print(
                    "   ✓ Найдены: "
                    + ", ".join(evaluation["keyword_hits"])
                )
            if evaluation["keyword_misses"]:
                print(
                    "   ✗ Не найдены: "
                    + ", ".join(evaluation["keyword_misses"])
                )
            if sources:
                print("📚 Источники: " + ", ".join(sorted(sources)))
            print("\n" + status)

            results.append({
                "id": q["id"],
                "group": q["group"],
                "query": q["query"],
                "entity": q["entity"],
                "answer": answer,
                "evaluation": evaluation,
                "sources": sorted(sources),
                "chunks_found": len(chunks),
                "elapsed_sec": elapsed,
                "test_pass": test_pass,
            })

        except Exception as e:
            print("❌ Ошибка: " + str(e))
            results.append({
                "id": q["id"],
                "group": q["group"],
                "query": q["query"],
                "entity": q["entity"],
                "answer": "ERROR: " + str(e),
                "evaluation": {
                    "keyword_hits": [],
                    "keyword_misses": q["expected_keywords"],
                    "coverage": 0.0,
                    "is_refusal": False,
                    "is_error": True,
                    "answer_length": 0,
                },
                "sources": [],
                "chunks_found": 0,
                "elapsed_sec": 0.0,
                "test_pass": False,
            })


def main():
    # Загружаем golden set
    with open(GOLDEN_SET_FILE, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    queries = golden_set["queries"]
    known_queries = [q for q in queries if q["group"] == "known"]
    absent_queries = [q for q in queries if q["group"] == "absent"]

    # Собираем уникальные файлы сущностей для удаления
    entity_files = sorted(set(q["entity_file"] for q in absent_queries))

    separator("ЗОЛОТОЙ НАБОР ТЕСТОВЫХ ЗАПРОСОВ")
    print("📋 Всего запросов: " + str(len(queries)))
    print("   Known (бот должен ответить): " + str(len(known_queries)))
    print("   Absent (бот не должен ответить полно): " + str(len(absent_queries)))
    print("\n🗑️  Сущности для удаления (" + str(len(entity_files)) + "):")
    for f in entity_files:
        print("   - " + f)

    # Проверяем, не остались ли файлы от предыдущего прерванного запуска
    if os.path.isdir(BACKUP_DIR) and os.listdir(BACKUP_DIR):
        print("\n⚠️  Обнаружены файлы от предыдущего прерванного запуска")
        leftover = os.listdir(BACKUP_DIR)
        restore_entities(leftover)
        separator("Пересборка индекса после восстановления")
        rebuild_index()

    results = []
    known_stats = {"total": 0, "pass": 0}
    absent_stats = {"total": 0, "pass": 0}
    removed = []

    try:
        # ============================================================
        # ФАЗА 1: Удаляем сущности → пересобираем индекс → absent
        # ============================================================
        separator("ФАЗА 1: Удаление сущностей из БЗ")
        removed = remove_entities(entity_files)

        separator("ФАЗА 1: Пересборка индекса (без удалённых сущностей)")
        rebuild_index()

        separator("ФАЗА 1: Загрузка RAG-движка (gapped KB)")
        rag = RAGEngine()
        rag.load()
        print(
            "✅ RAG-движок загружен (без "
            + str(len(removed)) + " сущностей)"
        )

        separator("ФАЗА 1: Absent-запросы (бот НЕ должен ответить полно)")
        run_queries(rag, absent_queries, results, known_stats, absent_stats)

        # Освобождаем ресурсы перед перезагрузкой
        del rag

    finally:
        # ============================================================
        # Гарантированное восстановление файлов (даже при ошибке)
        # ============================================================
        if removed:
            separator("ВОССТАНОВЛЕНИЕ: Возврат сущностей в БЗ")
            restore_entities(removed)

            separator("ВОССТАНОВЛЕНИЕ: Пересборка индекса (полная БЗ)")
            rebuild_index()

    # ================================================================
    # ФАЗА 2: Known-запросы на полной БЗ
    # ================================================================
    separator("ФАЗА 2: Загрузка RAG-движка (full KB)")
    rag = RAGEngine()
    rag.load()
    print("✅ RAG-движок загружен (полная БЗ)")

    separator("ФАЗА 2: Known-запросы (бот ДОЛЖЕН ответить)")
    run_queries(rag, known_queries, results, known_stats, absent_stats)

    # ================================================================
    # Итоги
    # ================================================================
    separator("ИТОГИ GOLDEN SET")

    total_pass = known_stats["pass"] + absent_stats["pass"]
    total = known_stats["total"] + absent_stats["total"]

    print(
        "\n📊 Known-запросы (бот должен ответить):     "
        + str(known_stats["pass"]) + "/" + str(known_stats["total"])
    )
    print(
        "📊 Absent-запросы (бот не должен ответить): "
        + str(absent_stats["pass"]) + "/" + str(absent_stats["total"])
    )

    icon = "✅" if total_pass == total else "⚠️"
    print(
        "\n" + icon + "  Общий результат: "
        + str(total_pass) + "/" + str(total)
    )

    # Сохраняем результаты
    report = {
        "total_queries": total,
        "known_pass": known_stats["pass"],
        "known_total": known_stats["total"],
        "absent_pass": absent_stats["pass"],
        "absent_total": absent_stats["total"],
        "removed_entities": entity_files,
        "results": results,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n💾 Результаты сохранены: " + RESULTS_FILE)


if __name__ == "__main__":
    main()
