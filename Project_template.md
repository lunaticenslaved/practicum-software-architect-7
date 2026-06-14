# RAG-система по фэнтезийной базе знаний

## Установка

```bash
make install
```

## Задания

### Task 1. Исследование технологий

**Что сделано:** сравнительный анализ LLM, эмбеддинг-моделей и векторных БД. Выбран стек: Ollama + llama3, intfloat/multilingual-e5-large, FAISS.

**Как проверить:** → `Task1/README.md`

---

### Task 2. Подготовка базы знаний

**Что сделано:** скрипты скачивания wiki-страниц и замены терминов (Naruto → фэнтезийный мир). Карта замен в `terms_map.json`, 34 файла в `knowledge_base/`.

**Как проверить:**

```bash
make prepare
```

→ `Task2/knowledge_base/*.txt`

---

### Task 3. Чанкинг, эмбеддинги, FAISS-индекс

**Что сделано:** разбиение текстов на чанки (800/150), генерация эмбеддингов (multilingual-e5-large), построение FAISS IndexFlatIP.

**Как проверить:**

```bash
make chunks
make index
make search QUERY="Who is Toren Solwind?"
```

→ `Task3/output/chunks.jsonl`, `Task3/output/embeddings.jsonl`, `Task3/faiss_index/`

---

### Task 4. RAG-бот (Telegram + CLI)

**Что сделано:** RAG-движок (`rag_engine.py`) с Few-shot и Chain-of-Thought промптингом. Telegram-бот и консольный клиент.

**Как проверить:**

```bash
make cli QUERY="What is The Obsidian Circle?"
make bot   # требует TELEGRAM_BOT_TOKEN
```

→ `Task4/rag_engine.py`, `Task4/bot.py`, `Task4/cli.py`

---

### Task 5. Тестирование промпт-инъекций

**Что сделано:** 10 тестов (5 полезных + 5 инъекций), автоматический цикл: инъекция → тест → очистка.

**Как проверить:**

```bash
make test
```

→ `Task5/kb_queries.json`, `Task5/injection_queries.json`, `Task5/test_rag.py`

---

### Task 6. Автоматическое обновление БЗ

**Что сделано:** инкрементальное обновление индекса — SHA-256 манифест, синхронизация `docs/` → `knowledge_base/`, чанкинг и эмбеддинг только изменённых файлов, cron-задача.

**Как проверить:**

```bash
cp new_file.txt Task6/docs/
make update-index
```

→ `Task6/logs/last_update_summary.json`, `Task6/logs/update_*.log`

---

### Task 7. Аналитика покрытия и качества БЗ

**Что сделано:** двухфазный golden set (13 запросов), JSONL-логирование всех запросов, метрики coverage/refusal/retrieval.

**Как проверить:**

```bash
make evaluate
```

→ `Task7/golden_questions_results.json`, `Task7/logs.jsonl`

---

## Запуск Telegram-бота через Docker

```bash
export TELEGRAM_BOT_TOKEN=your_token
docker compose up --build
```

Модель llama3 загружается автоматически при первом запуске (сервис `ollama-pull`).

Контейнеры:
- **ollama** — LLM-сервер
- **ollama-pull** — автоматическая загрузка модели llama3 (запускается один раз)
- **bot** — Python 3.10, Telegram-бот (`Task4/bot.py`) + FAISS-индекс
