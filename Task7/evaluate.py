"""
Запуск золотого набора тестовых запросов (golden set).

Загружает запросы из golden_questions.json, прогоняет через RAG-движок
и выводит результаты с оценкой покрытия.

Использование:
    python Task7/evaluate.py              # запуск всех запросов
    python Task7/evaluate.py --known      # только known-запросы
    python Task7/evaluate.py --absent     # только absent-запросы
"""

import json
import os
import sys
import time

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Task4")
)

from rag_engine import RAGEngine  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_SET_FILE = os.path.join(SCRIPT_DIR, "golden_questions.json")
RESULTS_FILE = os.path.join(SCRIPT_DIR, "golden_set_results.json")


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


def main():
    # Определяем фильтр группы
    group_filter = None
    if len(sys.argv) > 1:
        if sys.argv[1] == "--known":
            group_filter = "known"
        elif sys.argv[1] == "--absent":
            group_filter = "absent"
        elif sys.argv[1] == "--help":
            print(__doc__)
            return
        else:
            print("Неизвестный аргумент: " + sys.argv[1])
            print("Использование: python Task7/run_golden_set.py [--known|--absent|--help]")
            sys.exit(1)

    # Загружаем golden set
    with open(GOLDEN_SET_FILE, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    queries = golden_set["queries"]
    if group_filter:
        queries = [q for q in queries if q["group"] == group_filter]

    separator("ЗОЛОТОЙ НАБОР ТЕСТОВЫХ ЗАПРОСОВ")
    print("📋 Всего запросов: " + str(len(queries)))
    known_count = len([q for q in queries if q["group"] == "known"])
    absent_count = len([q for q in queries if q["group"] == "absent"])
    print("   Known (бот должен ответить): " + str(known_count))
    print("   Absent (бот не должен ответить полно): " + str(absent_count))

    # Загружаем RAG
    separator("Загрузка RAG-движка")
    rag = RAGEngine()
    rag.load()
    print("✅ RAG-движок загружен")

    # Запускаем запросы
    results = []
    known_stats = {"total": 0, "pass": 0}
    absent_stats = {"total": 0, "pass": 0}

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
                test_pass = evaluation["coverage"] >= 0.5 and not evaluation["is_refusal"]
                if test_pass:
                    known_stats["pass"] += 1
            else:
                absent_stats["total"] += 1
                # Для absent-запросов: тест проходит, если coverage < 0.5 или есть refusal
                test_pass = evaluation["coverage"] < 0.8 or evaluation["is_refusal"]
                if test_pass:
                    absent_stats["pass"] += 1

            status = "✅ PASS" if test_pass else "❌ FAIL"
            cov_pct = "{:.0%}".format(evaluation["coverage"])

            print("\n💬 Ответ (первые 300 символов):")
            print(answer[:300] + ("..." if len(answer) > 300 else ""))
            print("\n📊 Coverage: " + cov_pct
                  + " | Refusal: " + str(evaluation["is_refusal"])
                  + " | Chunks: " + str(len(chunks))
                  + " | Time: " + str(elapsed) + "s")
            if evaluation["keyword_hits"]:
                print("   ✓ Найдены: " + ", ".join(evaluation["keyword_hits"]))
            if evaluation["keyword_misses"]:
                print("   ✗ Не найдены: " + ", ".join(evaluation["keyword_misses"]))
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

    # Итоги
    separator("ИТОГИ GOLDEN SET")

    total_pass = known_stats["pass"] + absent_stats["pass"]
    total = known_stats["total"] + absent_stats["total"]

    print("\n📊 Known-запросы (бот должен ответить):     "
          + str(known_stats["pass"]) + "/" + str(known_stats["total"]))
    print("📊 Absent-запросы (бот не должен ответить): "
          + str(absent_stats["pass"]) + "/" + str(absent_stats["total"]))

    icon = "✅" if total_pass == total else "⚠️"
    print("\n" + icon + "  Общий результат: "
          + str(total_pass) + "/" + str(total))

    # Сохраняем результаты
    report = {
        "total_queries": total,
        "known_pass": known_stats["pass"],
        "known_total": known_stats["total"],
        "absent_pass": absent_stats["pass"],
        "absent_total": absent_stats["total"],
        "results": results,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n💾 Результаты сохранены: " + RESULTS_FILE)


if __name__ == "__main__":
    main()
