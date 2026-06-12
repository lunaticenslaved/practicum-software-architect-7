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

import json
import logging
import os
import sys

import faiss
import numpy as np
import requests
import torch
from transformers import AutoModel, AutoTokenizer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# Конфигурация
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FAISS_INDEX_DIR = os.path.join(SCRIPT_DIR, "..", "Task3", "faiss_index")
INDEX_FILE = os.path.join(FAISS_INDEX_DIR, "index.faiss")
METADATA_FILE = os.path.join(FAISS_INDEX_DIR, "metadata.json")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
TOP_K = int(os.environ.get("TOP_K", "5"))

# Модель для эмбеддингов запросов
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"
QUERY_PREFIX = "query: "

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============================================================
# Промпт с Few-shot и Chain-of-Thought
# ============================================================

# Few-shot примеры, извлечённые из реальных данных базы знаний:
#
# 1. Verdania.txt: «Verdania is the hidden village of the Realm of Embers.
#    As the village of one of the Five Great Sentinel Countries, Verdania has
#    a Archon as its leader known as the Archon, of which there have been
#    seven in its history.»
#
# 2. Toren_Solwind.txt: «Toren Solwind is a sentinel of Verdania's Solwind
#    clan and a reincarnation of Asura Ōtsutsuki. He became the beast-bearer
#    of the Crimson Beast on the day of his birth. … He soon proved to be one
#    of the main factors in winning the The Great Convergence War, leading him
#    to achieve his dream and become the village's Seventh Archon.»
#
# 3. The_Great_Convergence_War.txt: «The Great Convergence War was a conflict
#    between the Allied Sentinel Forces and The Obsidian Circle. The battle
#    began on the 8th of October and lasted until the 10th, with the complete
#    victory of the Allied Sentinel Forces.»

SYSTEM_PROMPT = """Ты — помощник по базе знаний фэнтези-мира. \
Ты отвечаешь на вопросы ТОЛЬКО на основе предоставленных фрагментов контекста. \
Если в контексте недостаточно информации для ответа, честно скажи об этом.

ВАЖНЫЕ ПРАВИЛА:
- Используй ТОЛЬКО информацию из контекста ниже.
- НЕ придумывай факты, которых нет в контексте.
- Если ответ охватывает несколько фрагментов контекста, синтезируй их.
- Отвечай на том же языке, на котором задан вопрос.

ТЕХНИКА (Chain-of-Thought): Ты помощник, который сначала размышляет, а потом отвечает. \
Всегда пиши свои шаги рассуждения в виде нумерованного списка, прежде чем дать финальный ответ. \
Формат ответа:
1. [Шаг рассуждения — что ты нашёл в контексте]
2. [Следующий шаг — какие факты связаны]
3. [Вывод — что следует из найденного]
Итого: [Финальный ответ]

Ниже приведены примеры ответов на вопросы. Эти примеры используют реальные факты \
из базы знаний (Few-shot):

---
Example 1:
Q: Где расположена Вердания и кто ей управляет?
A: Давайте разберёмся по шагам.
1. В базе знаний сказано, что Вердания — скрытая деревня Царства Углей (Realm of Embers).
2. Также указано, что деревней руководит Архонт (Archon), и за всю историю их было семь.
Итого: Вердания — скрытая деревня, расположенная в Царстве Углей. Ею управляет Архонт; всего в истории деревни было семь Архонтов.

---
Example 2:
Q: Who is Toren Solwind and what is he known for?
A: Let me reason step-by-step.
1. The knowledge base states that Toren Solwind is a sentinel of Verdania's Solwind clan.
2. He became the beast-bearer of the Crimson Beast on the day of his birth.
3. He proved to be one of the main factors in winning the Great Convergence War and became the village's Seventh Archon.
Final answer: Toren Solwind is a sentinel of Verdania's Solwind clan who became the beast-bearer of the Crimson Beast at birth. He played a key role in winning the Great Convergence War and ultimately achieved his dream of becoming the Seventh Archon.

---

Теперь ответь на вопрос пользователя, используя тот же подход: \
сначала пронумерованные шаги рассуждения на основе фрагментов контекста, затем финальный ответ."""


def build_rag_prompt(query: str, context_chunks: list[dict]) -> str:
    """
    Формирует промпт для LLM с контекстом из FAISS и техниками промптинга.

    Структура промпта (Q/A формат):
        1. Контекстные фрагменты из базы знаний
        2. Вопрос пользователя в формате Q: ...
        3. Инструкция для ответа в формате A: ...
    """
    # Собираем контекст из найденных чанков
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        source = chunk.get("metadata", {}).get("source", "unknown")
        text = chunk.get("text", "")
        context_parts.append(f"[Fragment {i} — {source}]\n{text}")

    context_text = "\n\n".join(context_parts)

    user_prompt = f"""Context fragments from the knowledge base:

{context_text}

---
Q: {query}
A: Let me reason step-by-step based on the context fragments above."""

    return user_prompt


# ============================================================
# Глобальные объекты (инициализируются при старте)
# ============================================================
class RAGEngine:
    """Инкапсулирует FAISS-индекс, модель эмбеддингов и Ollama-клиент."""

    def __init__(self):
        self.index = None
        self.metadata_store = None
        self.tokenizer = None
        self.model = None
        self.device = None

    def load(self):
        """Загружает FAISS-индекс и модель эмбеддингов."""
        # Проверяем файлы
        if not os.path.isfile(INDEX_FILE):
            logger.error(f"FAISS index not found: {INDEX_FILE}")
            sys.exit(1)
        if not os.path.isfile(METADATA_FILE):
            logger.error(f"Metadata file not found: {METADATA_FILE}")
            sys.exit(1)

        # Загружаем FAISS
        logger.info("Loading FAISS index...")
        self.index = faiss.read_index(INDEX_FILE)
        logger.info(f"FAISS index loaded: {self.index.ntotal} documents")

        # Загружаем метаданные
        logger.info("Loading metadata...")
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            self.metadata_store = json.load(f)
        logger.info(f"Metadata loaded: {len(self.metadata_store)} entries")

        # Загружаем модель эмбеддингов
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
        self.model = AutoModel.from_pretrained(EMBEDDING_MODEL_NAME).to(self.device)
        self.model.eval()
        logger.info(f"Embedding model loaded on {self.device}")

    def get_query_embedding(self, query: str) -> np.ndarray:
        """Генерирует эмбеддинг для поискового запроса."""
        text = QUERY_PREFIX + query

        encoded = self.tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**encoded)

        # Mean pooling
        last_hidden = outputs.last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).expand(last_hidden.size()).float()
        sum_embeddings = torch.sum(last_hidden * mask, dim=1)
        sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
        embedding = (sum_embeddings / sum_mask).squeeze(0)

        # L2-нормализация
        embedding = embedding / torch.clamp(torch.norm(embedding, p=2), min=1e-9)

        return embedding.cpu().numpy().astype(np.float32)

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        """Ищет ближайшие чанки в FAISS-индексе."""
        query_embedding = self.get_query_embedding(query)
        query_vector = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_vector)

        scores, indices = self.index.search(query_vector, top_k)

        results = []
        for rank in range(len(indices[0])):
            idx = indices[0][rank]
            if idx == -1:
                continue
            doc_id = str(idx)
            entry = self.metadata_store.get(doc_id, {})
            entry["score"] = float(scores[0][rank])
            results.append(entry)

        return results

    def generate_answer(self, query: str, context_chunks: list[dict]) -> str:
        """Отправляет промпт в Ollama и возвращает ответ LLM."""
        user_prompt = build_rag_prompt(query, context_chunks)

        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 1024,
            },
        }

        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "No response from LLM.")
        except requests.exceptions.ConnectionError:
            return (
                "❌ Не удалось подключиться к Ollama. "
                f"Убедитесь, что Ollama запущена на {OLLAMA_HOST} "
                f"и модель {OLLAMA_MODEL} загружена."
            )
        except requests.exceptions.Timeout:
            return "❌ Таймаут при ожидании ответа от LLM. Попробуйте позже."
        except Exception as e:
            return f"❌ Ошибка LLM: {e}"


# Глобальный экземпляр RAG-движка
rag = RAGEngine()


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
    await update.message.chat.send_action("typing")

    # 1. Поиск в FAISS
    try:
        chunks = rag.search(query, top_k=TOP_K)
    except Exception as e:
        logger.error(f"FAISS search error: {e}")
        await update.message.reply_text(f"❌ Ошибка поиска: {e}")
        return

    if not chunks:
        await update.message.reply_text(
            "🤷 Не удалось найти релевантные фрагменты в базе знаний."
        )
        return

    # 2. Формируем контекст и отправляем в LLM
    try:
        answer = rag.generate_answer(query, chunks)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        await update.message.reply_text(f"❌ Ошибка генерации ответа: {e}")
        return

    # 3. Формируем ответ с источниками
    sources = set()
    for chunk in chunks:
        src = chunk.get("metadata", {}).get("source", "")
        if src:
            sources.add(src.replace(".txt", "").replace("_", " "))

    sources_text = ", ".join(sorted(sources))
    response_text = f"{answer}\n\n📚 Источники: {sources_text}"

    # Telegram ограничивает длину сообщения 4096 символами
    if len(response_text) > 4096:
        response_text = response_text[:4090] + "..."

    await update.message.reply_text(response_text)


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

    # Создаём Telegram-бота
    print(f"🤖 Запуск Telegram-бота (модель: {OLLAMA_MODEL})...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("✅ Бот запущен! Ожидание сообщений...\n")
    app.run_polling()


if __name__ == "__main__":
    main()
