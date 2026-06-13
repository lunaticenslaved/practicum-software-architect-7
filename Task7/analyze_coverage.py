"""
Задание 7. Аналитика покрытия и качества базы знаний.

Скрипт выполняет полный цикл анализа:
  1. Создаёт резервные копии 3 ключевых сущностей
  2. Удаляет их из базы знаний
  3. Пересобирает FAISS-индекс
  4. Запускает golden set запросов (gap + control)
  5. Восстанавливает базу знаний и пересобирает индекс
  6. Запускает те же запросы повторно (baseline)
  7. Сравнивает результаты и формирует отчёт

Удаляемые сущности:
  - Rift_of_Echoes.txt  (место — 17 строк, ~10 перекрёстных ссылок)
  - Valdric.txt          (персонаж — 238 строк, ~139 перекрёстных ссылок)
  - The_Duskborne_Purge.txt (событие — 28 строк, ~25 перекрёстных ссылок)

Использование:
    python Task7/analyze_coverage.py              # полный анализ
    python Task7/analyze_coverage.py --dry-run    # только показать план
    python Task7/analyze_coverage.py --report     # показать последний отчёт

Переменные окружения:
    OLLAMA_HOST  — адрес Ollama (по умолчанию: http://localhost:11434)
    OLLAMA_MODEL — модель Ollama (по умолчанию: llama3)
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

# Добавляем Task4 в путь для импорта rag_engine
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Task4")
)

from rag_engine import RAGEngine  # noqa: E402

# ============================================================
# Конфигурация
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
KB_DIR = os.path.join(PROJECT_ROOT, "Task2", "knowledge_base")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backup")
REPORT_FILE = os.path.join(SCRIPT_DIR, "coverage_report.json")
PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")

# Сущности для удаления: (имя файла, тип, описание)
ENTITIES_TO_REMOVE = [
    {
        "file": "Rift_of_Echoes.txt",
        "type": "place",
        "name": "Rift of Echoes",
        "description": (
            "Ключевая локация — место двух битв Toren vs Kaelen, "
            "создана в битве Hashirama vs Theron. "
            "17 строк, ~10 перекрёстных ссылок."
        ),
    },
    {
        "file": "Valdric.txt",
        "type": "character",
        "name": "Valdric",
        "description": (
            "Один из Трёх Легенд, наставник Toren Solwind, "
            "также обучал Erevan и Auren. "
            "238 строк, ~139 перекрёстных ссылок в ~20 файлах."
        ),
    },
    {
        "file": "The_Duskborne_Purge.txt",
        "type": "event",
        "name": "The Duskborne Purge",
        "description": (
            "Массовое уничтожение клана Duskborne, совершённое "
            "Soren Duskborne и человеком, выдававшим себя за Theron. "
            "28 строк, ~25 перекрёстных ссылок в ~10 файлах."
        ),
    },
]


# ============================================================
# Golden Set: запросы для тестирования
# ============================================================

# Группа G (Gap) — запросы о УДАЛЁННЫХ сущностях.
GAP_QUERIES = [
    {
        "id": "G1",
        "query": "What is the Rift of Echoes and what battles took place there?",
        "entity": "Rift of Echoes",
        "entity_file": "Rift_of_Echoes.txt",
        "expected_keywords": [
            "rift of echoes", "valley", "toren", "kaelen",
            "hashirama", "theron", "battle",
        ],
        "description": "Прямой вопрос об удалённой локации.",
    },
    {
        "id": "G2",
        "query": (
            "Where did Toren Solwind and Kaelen Duskborne "
            "have their final battle?"
        ),
        "entity": "Rift of Echoes",
        "entity_file": "Rift_of_Echoes.txt",
        "expected_keywords": [
            "rift of echoes", "valley of the end", "final battle",
        ],
        "description": "Косвенный вопрос — ответ требует знания об удалённой локации.",
    },
    {
        "id": "G3",
        "query": "Who is Valdric and what role did he play in training Toren?",
        "entity": "Valdric",
        "entity_file": "Valdric.txt",
        "expected_keywords": [
            "valdric", "three legends", "toren", "mentor",
            "training", "toad", "spiralstrike",
        ],
        "description": "Прямой вопрос об удалённом персонаже.",
    },
    {
        "id": "G4",
        "query": "Who are the Three Legends and what are they known for?",
        "entity": "Valdric",
        "entity_file": "Valdric.txt",
        "expected_keywords": [
            "three legends", "valdric", "maelis", "vexaris",
            "legendary", "sentinel",
        ],
        "description": "Вопрос о группе, к которой принадлежит удалённый персонаж.",
    },
    {
        "id": "G5",
        "query": "What was the Duskborne Purge and who carried it out?",
        "entity": "The Duskborne Purge",
        "entity_file": "The_Duskborne_Purge.txt",
        "expected_keywords": [
            "duskborne purge", "massacre", "soren", "theron",
            "duskborne clan",
        ],
        "description": "Прямой вопрос об удалённом событии.",
    },
    {
        "id": "G6",
        "query": "Why did Soren Duskborne kill his own clan?",
        "entity": "The Duskborne Purge",
        "entity_file": "The_Duskborne_Purge.txt",
        "expected_keywords": [
            "soren", "duskborne", "clan", "purge", "massacre",
            "verdania", "coup", "protect",
        ],
        "description": "Косвенный вопрос — ответ требует знания об удалённом событии.",
    },
]

# Группа C (Control) — запросы о сущностях, которые НЕ удалены.
CONTROL_QUERIES = [
    {
        "id": "C1",
        "query": "Who is Toren Solwind and what is he known for?",
        "entity": "Toren Solwind",
        "entity_file": "Toren_Solwind.txt",
        "expected_keywords": [
            "toren", "solwind", "sentinel", "verdania",
            "crimson beast", "archon",
        ],
        "description": "Контрольный запрос — главный персонаж (не удалён).",
    },
    {
        "id": "C2",
        "query": "What is The Obsidian Circle and what are their goals?",
        "entity": "The Obsidian Circle",
        "entity_file": "The_Obsidian_Circle.txt",
        "expected_keywords": [
            "obsidian circle", "criminal", "primal beasts",
            "sentinel", "organization",
        ],
        "description": "Контрольный запрос — организация (не удалена).",
    },
    {
        "id": "C3",
        "query": "Где расположена Вердания и кто ей управляет?",
        "entity": "Verdania",
        "entity_file": "Verdania.txt",
        "expected_keywords": [
            "verdania", "realm of embers", "archon",
            "hidden village",
        ],
        "description": "Контрольный запрос на русском — локация (не удалена).",
    },
    {
        "id": "C4",
        "query": "What was The Great Convergence War and who fought in it?",
        "entity": "The Great Convergence War",
        "entity_file": "The_Great_Convergence_War.txt",
        "expected_keywords": [
            "great convergence war", "allied sentinel",
            "obsidian circle", "war",
        ],
        "description": "Контрольный запрос — событие (не удалено).",
    },
]

ALL_QUERIES = GAP_QUERIES + CONTROL_QUERIES


# ============================================================
# Вспомогательные функции
# ============================================================

def separator(title):
    """Печатает разделитель с заголовком."""
    print("\n" + "=" * 70)
    print("  " + title)
    print("=" * 70)


def rebuild_index():
    """Пересобирает FAISS-индекс (chunking -> embeddings -> index)."""
    print("🔄 Пересборка индекса (chunking -> embeddings -> index)...")
    for script in [
        "Task3/01_chunking.py",
        "Task3/02_embeddings.py",
        "Task3/03_index.py",
    ]:
        print("   ▸ " + script)
        result = subprocess.run(
            [PYTHON, script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("   ❌ Ошибка: " + result.stderr)
            return False
    print("✅ Индекс пересобран")
    return True


def backup_entities():
    """Создаёт резервные копии файлов сущностей."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for entity in ENTITIES_TO_REMOVE:
        src = os.path.join(KB_DIR, entity["file"])
        dst = os.path.join(BACKUP_DIR, entity["file"])
        if not os.path.isfile(src):
            print("❌ Файл не найден: " + src)
            return False
        shutil.copy2(src, dst)
        print("   📦 " + entity["file"] + " -> backup/")
    return True


def remove_entities():
    """Удаляет файлы сущностей из базы знаний."""
    for entity in ENTITIES_TO_REMOVE:
        path = os.path.join(KB_DIR, entity["file"])
        if os.path.isfile(path):
            os.remove(path)
            print("   🗑️  Удалён: " + entity["file"])


def restore_entities():
    """Восстанавливает файлы сущностей из резервных копий."""
    for entity in ENTITIES_TO_REMOVE:
        src = os.path.join(BACKUP_DIR, entity["file"])
        dst = os.path.join(KB_DIR, entity["file"])
        if not os.path.isfile(src):
            print("❌ Резервная копия не найдена: " + src)
            return False
        shutil.copy2(src, dst)
        print("   ♻️  Восстановлен: " + entity["file"])
    return True


def evaluate_answer(answer, expected_keywords):
    """
    Оценивает качество ответа по наличию ожидаемых ключевых слов.

    Возвращает dict с полями:
        keyword_hits, keyword_misses, coverage, is_refusal, answer_length
    """
    answer_lower = answer.lower()

    refusal_markers = [
        "не нашёл", "не найден", "не знаю", "нет информации",
        "no information", "cannot answer", "don't have",
        "not found", "no relevant", "недостаточно информации",
        "insufficient information", "не содержит",
        "does not contain", "нет данных", "no data",
        "не могу ответить", "cannot provide",
    ]
    is_refusal = any(m in answer_lower for m in refusal_markers)

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
        "answer_length": len(answer),
    }


def evaluate_retrieval(chunks, entity_file):
    """
    Оценивает качество поиска (retrieval).

    Возвращает dict с полями:
        has_target_source, target_chunks, total_chunks,
        avg_score, max_score, sources
    """
    target_chunks = 0
    scores = []
    sources = set()

    for chunk in chunks:
        src = chunk.get("metadata", {}).get("source", "")
        score = chunk.get("score", 0.0)
        sources.add(src)
        scores.append(score)
        if src == entity_file:
            target_chunks += 1

    return {
        "has_target_source": target_chunks > 0,
        "target_chunks": target_chunks,
        "total_chunks": len(chunks),
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "max_score": round(max(scores), 4) if scores else 0.0,
        "sources": sorted(sources),
    }


def run_queries(rag, queries, label):
    """Запускает набор запросов через RAG-движок."""
    results = []

    for q in queries:
        short_query = q["query"][:60]
        print("\n   [" + q["id"] + "] " + short_query + "...")
        start = time.time()

        try:
            rag_result = rag.ask(q["query"])
            elapsed = round(time.time() - start, 2)

            answer = rag_result["answer"]
            chunks = rag_result["chunks"]

            answer_eval = evaluate_answer(answer, q["expected_keywords"])
            retrieval_eval = evaluate_retrieval(chunks, q["entity_file"])

            if answer_eval["is_refusal"]:
                status = "🚫"
            elif answer_eval["coverage"] >= 0.5:
                status = "✅"
            else:
                status = "⚠️"

            ret_mark = "✓" if retrieval_eval["has_target_source"] else "✗"
            cov_pct = "{:.0%}".format(answer_eval["coverage"])
            print(
                "        " + status
                + " coverage=" + cov_pct
                + " refusal=" + str(answer_eval["is_refusal"])
                + " retrieval=" + ret_mark
                + " time=" + str(elapsed) + "s"
            )

            results.append({
                "id": q["id"],
                "query": q["query"],
                "entity": q["entity"],
                "entity_file": q["entity_file"],
                "description": q["description"],
                "label": label,
                "answer": answer,
                "answer_eval": answer_eval,
                "retrieval_eval": retrieval_eval,
                "elapsed_sec": elapsed,
            })

        except Exception as e:
            print("        ❌ Ошибка: " + str(e))
            results.append({
                "id": q["id"],
                "query": q["query"],
                "entity": q["entity"],
                "entity_file": q["entity_file"],
                "description": q["description"],
                "label": label,
                "answer": "ERROR: " + str(e),
                "answer_eval": {
                    "keyword_hits": [],
                    "keyword_misses": q["expected_keywords"],
                    "coverage": 0.0,
                    "is_refusal": False,
                    "answer_length": 0,
                },
                "retrieval_eval": {
                    "has_target_source": False,
                    "target_chunks": 0,
                    "total_chunks": 0,
                    "avg_score": 0.0,
                    "max_score": 0.0,
                    "sources": [],
                },
                "elapsed_sec": 0.0,
            })

    return results


def compute_metrics(results):
    """Вычисляет агрегированные метрики по результатам."""
    if not results:
        return {}

    coverages = [r["answer_eval"]["coverage"] for r in results]
    refusals = [1 if r["answer_eval"]["is_refusal"] else 0 for r in results]
    retrieval_hits = [
        1 if r["retrieval_eval"]["has_target_source"] else 0
        for r in results
    ]
    scores = [r["retrieval_eval"]["avg_score"] for r in results]
    lengths = [r["answer_eval"]["answer_length"] for r in results]

    n = len(results)
    return {
        "total_queries": n,
        "avg_coverage": round(sum(coverages) / n, 3),
        "refusal_rate": round(sum(refusals) / n, 3),
        "retrieval_hit_rate": round(sum(retrieval_hits) / n, 3),
        "avg_score": round(sum(scores) / n, 4),
        "avg_answer_length": round(sum(lengths) / n, 1),
    }


def fmt_pct(value):
    """Форматирует число как процент."""
    return "{:.1%}".format(value)


def print_comparison(gap_before, gap_after, ctrl_before, ctrl_after):
    """Печатает сравнительную таблицу метрик."""
    separator("СРАВНИТЕЛЬНЫЙ АНАЛИЗ")

    header = (
        "\n{:<25} {:>14} {:>14} {:>10}".format(
            "Метрика", "С пробелами", "Без пробелов", "Delta"
        )
    )
    print(header)
    print("-" * 65)

    def row(name, v1, v2):
        delta = v2 - v1
        sign = "+" if delta > 0 else ""
        print(
            "{:<25} {:>14} {:>14} {:>10}".format(
                name, fmt_pct(v1), fmt_pct(v2), sign + fmt_pct(delta)
            )
        )

    print("--- Gap-запросы ---")
    row("  Keyword coverage", gap_before["avg_coverage"], gap_after["avg_coverage"])
    row("  Refusal rate", gap_before["refusal_rate"], gap_after["refusal_rate"])
    row(
        "  Retrieval hit rate",
        gap_before["retrieval_hit_rate"],
        gap_after["retrieval_hit_rate"],
    )

    print("--- Control-запросы ---")
    row("  Keyword coverage", ctrl_before["avg_coverage"], ctrl_after["avg_coverage"])
    row("  Refusal rate", ctrl_before["refusal_rate"], ctrl_after["refusal_rate"])
    row(
        "  Retrieval hit rate",
        ctrl_before["retrieval_hit_rate"],
        ctrl_after["retrieval_hit_rate"],
    )


# ============================================================
# Основной процесс
# ============================================================

def run_analysis():
    """Выполняет полный цикл анализа покрытия."""
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "entities_removed": [e["name"] for e in ENTITIES_TO_REMOVE],
        "entities_details": ENTITIES_TO_REMOVE,
        "phases": {},
    }
    total_start = time.time()

    # -- Фаза 1: Резервное копирование --
    separator("ФАЗА 1: Резервное копирование сущностей")
    print("📦 Создание резервных копий в backup/")
    if not backup_entities():
        print("❌ Не удалось создать резервные копии. Прерывание.")
        sys.exit(1)
    print("✅ Резервные копии созданы")

    # -- Фаза 2: Удаление сущностей --
    separator("ФАЗА 2: Удаление сущностей из базы знаний")
    print("🗑️  Удаление файлов:")
    remove_entities()

    remaining = [
        e["file"] for e in ENTITIES_TO_REMOVE
        if os.path.isfile(os.path.join(KB_DIR, e["file"]))
    ]
    if remaining:
        print("❌ Файлы не удалены: " + str(remaining))
        restore_entities()
        sys.exit(1)

    kb_files = sorted(f for f in os.listdir(KB_DIR) if f.endswith(".txt"))
    print("📂 Файлов в KB после удаления: " + str(len(kb_files)))

    # -- Фаза 3: Пересборка индекса (с пробелами) --
    separator("ФАЗА 3: Пересборка индекса (с пробелами)")
    if not rebuild_index():
        print("❌ Ошибка пересборки. Восстанавливаем KB...")
        restore_entities()
        rebuild_index()
        sys.exit(1)

    # -- Фаза 4: Тестирование с пробелами --
    separator("ФАЗА 4: Тестирование с пробелами в базе знаний")
    print("🔄 Загрузка RAG-движка...")
    rag = RAGEngine()
    rag.load()
    print("✅ RAG-движок загружен\n")

    print("📋 Gap-запросы (о удалённых сущностях):")
    gap_results_before = run_queries(rag, GAP_QUERIES, "gap_with_holes")

    print("\n📋 Control-запросы (о сохранённых сущностях):")
    ctrl_results_before = run_queries(rag, CONTROL_QUERIES, "control_with_holes")

    del rag

    report["phases"]["with_gaps"] = {
        "gap_results": gap_results_before,
        "control_results": ctrl_results_before,
        "gap_metrics": compute_metrics(gap_results_before),
        "control_metrics": compute_metrics(ctrl_results_before),
    }

    # -- Фаза 5: Восстановление базы знаний --
    separator("ФАЗА 5: Восстановление базы знаний")
    print("♻️  Восстановление файлов:")
    if not restore_entities():
        print("❌ Не удалось восстановить файлы!")
        sys.exit(1)

    kb_files = sorted(f for f in os.listdir(KB_DIR) if f.endswith(".txt"))
    print("📂 Файлов в KB после восстановления: " + str(len(kb_files)))

    # -- Фаза 6: Пересборка индекса (полная KB) --
    separator("ФАЗА 6: Пересборка индекса (полная KB)")
    if not rebuild_index():
        print("❌ Ошибка пересборки!")
        sys.exit(1)

    # -- Фаза 7: Тестирование без пробелов (baseline) --
    separator("ФАЗА 7: Тестирование без пробелов (baseline)")
    print("🔄 Загрузка RAG-движка...")
    rag = RAGEngine()
    rag.load()
    print("✅ RAG-движок загружен\n")

    print("📋 Gap-запросы (те же, но KB полная):")
    gap_results_after = run_queries(rag, GAP_QUERIES, "gap_full_kb")

    print("\n📋 Control-запросы (те же, KB полная):")
    ctrl_results_after = run_queries(rag, CONTROL_QUERIES, "control_full_kb")

    del rag

    report["phases"]["full_kb"] = {
        "gap_results": gap_results_after,
        "control_results": ctrl_results_after,
        "gap_metrics": compute_metrics(gap_results_after),
        "control_metrics": compute_metrics(ctrl_results_after),
    }

    # -- Фаза 8: Сравнительный анализ --
    gap_m_before = report["phases"]["with_gaps"]["gap_metrics"]
    gap_m_after = report["phases"]["full_kb"]["gap_metrics"]
    ctrl_m_before = report["phases"]["with_gaps"]["control_metrics"]
    ctrl_m_after = report["phases"]["full_kb"]["control_metrics"]

    print_comparison(gap_m_before, gap_m_after, ctrl_m_before, ctrl_m_after)

    # -- Итоговые выводы --
    separator("ИТОГОВЫЕ ВЫВОДЫ")

    gap_coverage_drop = gap_m_after["avg_coverage"] - gap_m_before["avg_coverage"]
    ctrl_coverage_drop = ctrl_m_after["avg_coverage"] - ctrl_m_before["avg_coverage"]

    conclusions = []

    if gap_coverage_drop > 0.1:
        msg = (
            "Удаление сущностей значительно снизило качество ответов "
            "на gap-запросы (coverage: "
            + fmt_pct(gap_m_before["avg_coverage"]) + " -> "
            + fmt_pct(gap_m_after["avg_coverage"])
            + ", delta=" + fmt_pct(gap_coverage_drop)
            + "). Это подтверждает, что удалённые сущности были важны для KB."
        )
        conclusions.append("✅ " + msg)
    else:
        msg = (
            "Удаление сущностей не сильно повлияло на gap-запросы "
            "(coverage: "
            + fmt_pct(gap_m_before["avg_coverage"]) + " -> "
            + fmt_pct(gap_m_after["avg_coverage"])
            + "). Возможно, информация дублируется в других файлах."
        )
        conclusions.append("⚠️  " + msg)

    if abs(ctrl_coverage_drop) < 0.1:
        msg = (
            "Control-запросы не пострадали от удаления "
            "(coverage: "
            + fmt_pct(ctrl_m_before["avg_coverage"]) + " -> "
            + fmt_pct(ctrl_m_after["avg_coverage"])
            + "). Пробелы локализованы и не влияют на остальную KB."
        )
        conclusions.append("✅ " + msg)
    else:
        msg = (
            "Control-запросы также пострадали "
            "(coverage: "
            + fmt_pct(ctrl_m_before["avg_coverage"]) + " -> "
            + fmt_pct(ctrl_m_after["avg_coverage"])
            + "). Удалённые сущности имели широкое влияние на KB."
        )
        conclusions.append("⚠️  " + msg)

    # Retrieval analysis
    gap_ret_before = gap_m_before["retrieval_hit_rate"]
    gap_ret_after = gap_m_after["retrieval_hit_rate"]
    if gap_ret_after > gap_ret_before:
        msg = (
            "Retrieval hit rate для gap-запросов вырос с "
            + fmt_pct(gap_ret_before) + " до "
            + fmt_pct(gap_ret_after)
            + " после восстановления KB. FAISS корректно находит "
            "целевые документы при их наличии."
        )
        conclusions.append("✅ " + msg)

    for c in conclusions:
        print("\n" + c)

    report["conclusions"] = conclusions
    report["duration_sec"] = round(time.time() - total_start, 1)

    # Сохраняем отчёт
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n💾 Отчёт сохранён: " + REPORT_FILE)

    return report


def show_dry_run():
    """Показывает план анализа без выполнения."""
    separator("DRY RUN — План анализа покрытия")

    print("\n📋 Сущности для удаления:")
    for i, entity in enumerate(ENTITIES_TO_REMOVE, 1):
        print(
            "   " + str(i) + ". " + entity["name"]
            + " (" + entity["type"] + ") — " + entity["file"]
        )
        print("      " + entity["description"])

    print("\n📋 Golden Set — Gap-запросы (" + str(len(GAP_QUERIES)) + " шт.):")
    for q in GAP_QUERIES:
        print("   [" + q["id"] + "] " + q["query"])
        print("      Сущность: " + q["entity"] + " | " + q["description"])

    ctrl_count = str(len(CONTROL_QUERIES))
    print("\n📋 Golden Set — Control-запросы (" + ctrl_count + " шт.):")
    for q in CONTROL_QUERIES:
        print("   [" + q["id"] + "] " + q["query"])
        print("      Сущность: " + q["entity"] + " | " + q["description"])

    print("\n📋 Этапы анализа:")
    print("   1. Резервное копирование сущностей")
    print("   2. Удаление сущностей из KB")
    print("   3. Пересборка FAISS-индекса (с пробелами)")
    print("   4. Запуск golden set (с пробелами)")
    print("   5. Восстановление KB")
    print("   6. Пересборка FAISS-индекса (полная KB)")
    print("   7. Запуск golden set (baseline)")
    print("   8. Сравнительный анализ и отчёт")


def show_report():
    """Показывает последний сохранённый отчёт."""
    if not os.path.isfile(REPORT_FILE):
        print("❌ Отчёт не найден: " + REPORT_FILE)
        print("   Сначала запустите: python Task7/analyze_coverage.py")
        sys.exit(1)

    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        report = json.load(f)

    separator("ОТЧЁТ О ПОКРЫТИИ БАЗЫ ЗНАНИЙ")
    print("\n📅 Дата: " + report["timestamp"])
    print("⏱️  Длительность: " + str(report.get("duration_sec", "?")) + " сек")
    print("🗑️  Удалённые сущности: " + ", ".join(report["entities_removed"]))

    for phase_name in ["with_gaps", "full_kb"]:
        phase = report["phases"].get(phase_name, {})
        if not phase:
            continue

        label = "С пробелами" if phase_name == "with_gaps" else "Без пробелов"
        separator("Фаза: " + label)

        for group_name in ["gap_metrics", "control_metrics"]:
            metrics = phase.get(group_name, {})
            if not metrics:
                continue
            group_label = "Gap" if "gap" in group_name else "Control"
            print("\n  " + group_label + "-запросы:")
            print("    Queries:            " + str(metrics.get("total_queries", 0)))
            print("    Avg coverage:       " + fmt_pct(metrics.get("avg_coverage", 0)))
            print("    Refusal rate:       " + fmt_pct(metrics.get("refusal_rate", 0)))
            print("    Retrieval hit rate: " + fmt_pct(metrics.get("retrieval_hit_rate", 0)))
            print("    Avg score:          " + str(metrics.get("avg_score", 0)))

    if "conclusions" in report:
        separator("ВЫВОДЫ")
        for c in report["conclusions"]:
            print("\n" + c)


def main():
    """Точка входа."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--dry-run":
            show_dry_run()
            return
        elif sys.argv[1] == "--report":
            show_report()
            return
        elif sys.argv[1] == "--help":
            print(__doc__)
            return
        else:
            print("Неизвестный аргумент: " + sys.argv[1])
            print("Использование: python Task7/analyze_coverage.py [--dry-run|--report|--help]")
            sys.exit(1)

    run_analysis()


if __name__ == "__main__":
    main()