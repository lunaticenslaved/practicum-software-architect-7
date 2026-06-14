# RAG Telegram-бот и консольный клиент

## Архитектура

```
Запрос → Query Embedding (e5-large) → FAISS Search (top-5) → Prompt (Few-shot + CoT) → Llama 3 (Ollama) → Ответ
```

## Структура файлов

| Файл | Описание |
|------|----------|
| `rag_engine.py` | RAG-движок: FAISS-поиск, эмбеддинги, промпт, Ollama |
| `bot.py` | Telegram-бот |
| `cli.py` | Консольный клиент (REPL / одиночный запрос) |

## Техники промптинга

### Few-shot

2 примера Q/A из реальных данных БЗ (`Verdania.txt`, `Toren_Solwind.txt`) + 1 пример защиты от промпт-инъекции.

### Chain-of-Thought

Модель рассуждает пошагово перед ответом:
1. Анализ контекстных фрагментов
2. Выделение релевантных фактов
3. Синтез ответа

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота |
| `OLLAMA_HOST` | `http://localhost:11434` | Адрес Ollama API |
| `OLLAMA_MODEL` | `llama3` | Модель для генерации |
| `TOP_K` | `5` | Количество чанков контекста |

## Запуск

```bash
# Ollama
ollama pull llama3 && ollama serve

# Консольный клиент
make cli
make cli QUERY="Who is Toren Solwind?"

# Telegram-бот
export TELEGRAM_BOT_TOKEN="your-token"
make bot
```
