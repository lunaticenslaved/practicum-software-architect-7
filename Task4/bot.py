"""
RAG Telegram-бот с техниками промптинга (Few-shot + Chain-of-Thought).

Пайплайн:
1. Получает текстовый запрос пользователя из Telegram.
2. Преобразует запрос в эмбеддинг (intfloat/multilingual-e5-large).
3. Ищет ближайшие чанки в FAISS-индексе.
4. Формирует промпт с найденными фрагментами + Few-shot + CoT.
5. Отправляет промпт в Llama 3 через Ollama.
6. Возвращает ответ пользователю в Telegram.

Переменные окружения:
    TELEGRAM_BOT_TOKEN — токен Telegram-бота (обязательно)
    OLLAMA_HOST        — адрес Ollama (по умолчанию: http://localhost:11434)
    OLLAMA_MODEL       — модель Ollama (по умолчанию: llama3)
    TOP_K              — количество чанков для контекста (по умолчанию: 5)
"""

import asyncio
import functools
import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from rag_engine import RAGEngine, OLLAMA_MODEL

# ============================================================
# Конфигурация
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Глобальный экземпляр RAG-движка
rag = RAGEngine()


# ============================================================
# Утилиты
# ============================================================
async def send_typing_safe(chat) -> None:
    """Отправляет typing action, игнорируя ошибки сети."""
    try:
        await chat.send_action("typing")
    except Exception:
        pass


async def reply_with_retry(message, text: str, retries: int = 3) -> None:
    """Отправляет ответ с повторными попытками при таймауте."""
    for attempt in range(retries):
        try:
            await message.reply_text(text)
            return
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Reply attempt {attempt + 1} failed: {e}, retrying...")
                await asyncio.sleep(2)
            else:
                logger.error(f"Reply failed after {retries} attempts: {e}")
                raise


# ============================================================
# Обработчики Telegram
# ============================================================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "👋 Привет! Я RAG-бот по базе знаний фэнтези-мира.\n\n"
        "Задайте мне вопрос, и я найду ответ в базе знаний.\n\n"
        "Примеры вопросов:\n"
        "• Who is Toren Solwind?\n"
        "• Tell me about the Great Convergence War\n"
        "• What is Verdania?\n"
        "• Describe the Duskborne clan\n\n"
        "Команды:\n"
        "/start — показать это сообщение\n"
        "/help — помощь"
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    await update.message.reply_text(
        "🔍 Как я работаю:\n\n"
        "1. Ваш вопрос преобразуется в эмбеддинг (multilingual-e5-large)\n"
        "2. Ищу похожие фрагменты в базе знаний (FAISS)\n"
        "3. Формирую промпт с контекстом (Few-shot + Chain-of-Thought)\n"
        "4. Отправляю в LLM (Llama 3 через Ollama)\n"
        "5. Возвращаю ответ вам\n\n"
        "Просто напишите вопрос текстом!"
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений — основной RAG-пайплайн."""
    query = update.message.text.strip()
    if not query:
        return

    logger.info(f"Query from {update.effective_user.id}: {query}")

    # Отправляем индикатор "печатает..."
    await send_typing_safe(update.message.chat)

    # RAG-пайплайн: запускаем в executor, чтобы не блокировать event loop,
    # и параллельно отправляем typing action каждые 4 секунды
    loop = asyncio.get_event_loop()
    result = None

    try:
        rag_future = loop.run_in_executor(
            None, functools.partial(rag.ask, query)
        )

        # Периодически отправляем typing, пока Ollama думает
        while not rag_future.done():
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(rag_future), timeout=4.0
                )
                break
            except asyncio.TimeoutError:
                # Ollama ещё думает — отправляем typing action
                await send_typing_safe(update.message.chat)

        if result is None:
            result = rag_future.result()

    except Exception as e:
        logger.error(f"RAG error: {e}")
        await reply_with_retry(update.message, f"❌ Ошибка: {e}")
        return

    answer = result["answer"]
    sources = result["sources"]

    sources_text = ", ".join(sorted(sources)) if sources else "—"
    response_text = f"{answer}\n\n📚 Источники: {sources_text}"

    # Telegram ограничивает длину сообщения 4096 символами
    if len(response_text) > 4096:
        response_text = response_text[:4090] + "..."

    await reply_with_retry(update.message, response_text)


# ============================================================
# Точка входа
# ============================================================
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Переменная окружения TELEGRAM_BOT_TOKEN не задана!")
        print("   Установите: export TELEGRAM_BOT_TOKEN='your-token-here'")
        sys.exit(1)

    # Загружаем RAG-движок
    print("🔄 Загрузка RAG-движка...")
    rag.load()
    print("✅ RAG-движок загружен!\n")

    # Создаём Telegram-бота с увеличенными таймаутами
    print(f"🤖 Запуск Telegram-бота (модель: {OLLAMA_MODEL})...")
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("✅ Бот запущен! Ожидание сообщений...\n")
    app.run_polling()


if __name__ == "__main__":
    main()
