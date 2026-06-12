"""
Консольный RAG-клиент с техниками промптинга (Few-shot + Chain-of-Thought).

Пайплайн (тот же, что и в Telegram-боте):
1. Получает текстовый запрос пользователя из stdin.
2. Преобразует запрос в эмбеддинг (intfloat/multilingual-e5-large).
3. Ищет ближайшие чанки в FAISS-индексе.
4. Формирует промпт с найденными фрагментами + Few-shot + CoT.
5. Отправляет промпт в Llama 3 через Ollama.
6. Выводит ответ в stdout.

Использование:
    python Task4/cli.py                  # интерактивный режим (REPL)
    python Task4/cli.py "Who is Toren?"  # одиночный запрос

Переменные окружения:
    OLLAMA_HOST  — адрес Ollama (по умолчанию: http://localhost:11434)
    OLLAMA_MODEL — модель Ollama (по умолчанию: llama3)
    TOP_K        — количество чанков для контекста (по умолчанию: 5)
"""

import logging
import sys

from rag_engine import RAGEngine, OLLAMA_MODEL

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def print_result(result: dict) -> None:
    """Выводит результат RAG-запроса в консоль."""
    print()
    print(result["answer"])

    sources = result["sources"]
    if sources:
        sources_text = ", ".join(sorted(sources))
        print(f"\n📚 Источники: {sources_text}")

    print()


def single_query(rag: RAGEngine, query: str) -> None:
    """Выполняет одиночный запрос и выводит результат."""
    print(f"\n🔍 Запрос: {query}")
    print("⏳ Поиск и генерация ответа...")

    try:
        result = rag.ask(query)
        print_result(result)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}\n")
        sys.exit(1)


def interactive_mode(rag: RAGEngine) -> None:
    """Интерактивный REPL-режим: читает запросы из stdin в цикле."""
    print("=" * 60)
    print("  RAG-клиент (интерактивный режим)")
    print(f"  Модель: {OLLAMA_MODEL}")
    print("  Введите вопрос и нажмите Enter.")
    print("  Для выхода: quit, exit или Ctrl+C")
    print("=" * 60)

    while True:
        try:
            query = input("\n❓ Вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 До свидания!")
            break

        if not query:
            continue

        if query.lower() in ("quit", "exit", "q"):
            print("\n👋 До свидания!")
            break

        print("⏳ Поиск и генерация ответа...")

        try:
            result = rag.ask(query)
            print_result(result)
        except Exception as e:
            print(f"\n❌ Ошибка: {e}\n")


def main() -> None:
    # Загружаем RAG-движок
    print("🔄 Загрузка RAG-движка...")
    rag = RAGEngine()
    rag.load()
    print("✅ RAG-движок загружен!\n")

    # Если передан аргумент — одиночный запрос, иначе — REPL
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        single_query(rag, query)
    else:
        interactive_mode(rag)


if __name__ == "__main__":
    main()
