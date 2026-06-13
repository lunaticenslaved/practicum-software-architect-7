# Задание 7. Аналитика покрытия и качества базы знаний

## Цель

Оценить полноту и актуальность базы знаний, выявить темы, по которым бот не сможет дать ответы, и обоснованно улучшить покрытие.

## Методология

### 1. Двухфазный прогон golden set

Скрипт `evaluate.py` выполняет двухфазный прогон для корректной оценки поведения бота:

**Фаза 1 — Absent-запросы (бот НЕ должен ответить полно):**
1. Удаляет 3 файла сущностей из `Task2/knowledge_base/` во временную папку `backup/`
2. Пересобирает FAISS-индекс (chunking → embeddings → index)
3. Загружает RAG-движок с неполной БЗ
4. Запускает 5 absent-запросов — проверяет, что бот не может дать полный ответ

**Фаза 2 — Known-запросы (бот ДОЛЖЕН ответить):**
1. Восстанавливает файлы из `backup/` обратно в БЗ
2. Пересобирает FAISS-индекс (полная БЗ)
3. Загружает RAG-движок с полной БЗ
4. Запускает 8 known-запросов — проверяет, что бот даёт полные ответы

### 2. Удалённые сущности

Для тестирования поведения бота при отсутствии информации удаляются 3 сущности разных типов:

| Файл | Сущность | Тип | Размер |
|------|----------|-----|--------|
| `Rift_of_Echoes.txt` | Rift of Echoes | локация | 17 строк |
| `Valdric.txt` | Valdric | персонаж | 238 строк |
| `The_Duskborne_Purge.txt` | The Duskborne Purge | событие | 28 строк |

### 3. Golden Set — тестовые запросы

Золотой набор из 13 запросов хранится в `golden_questions.json` и разделён на две группы:

#### Группа Known (K) — 8 запросов на известные темы (бот должен ответить)

| ID | Запрос | Целевая сущность | Аспект |
|----|--------|------------------|--------|
| K1 | Who is Toren Solwind and what is he known for? | Toren Solwind | персонаж |
| K2 | What is The Obsidian Circle and what are their goals? | The Obsidian Circle | организация |
| K3 | Где расположена Вердания и кто ей управляет? | Verdania | локация (рус.) |
| K4 | What was The Great Convergence War and who fought in it? | The Great Convergence War | событие |
| K5 | Who is Kaelen Duskborne and what is his relationship with Toren? | Kaelen Duskborne | персонаж |
| K6 | Who is Zephros and what is his role as Sand Archon? | Zephros | персонаж |
| K7 | What happened to Soren Duskborne and why did he betray his clan? | Soren Duskborne | персонаж |
| K8 | Who is Theron Duskborne and why is he considered legendary? | Theron Duskborne | персонаж |

#### Группа Absent (A) — 5 запросов на удалённые/отсутствующие темы (бот не должен ответить полно)

| ID | Запрос | Целевая сущность | Тип вопроса |
|----|--------|------------------|-------------|
| A1 | What is the Rift of Echoes and what battles took place there? | Rift of Echoes | прямой |
| A2 | Who is Valdric and what role did he play in training Toren? | Valdric | прямой |
| A3 | What was the Duskborne Purge and who carried it out? | The Duskborne Purge | прямой |
| A4 | Where did Toren and Kaelen have their final battle? | Rift of Echoes | косвенный |
| A5 | Who are the Three Legends and what are they known for? | Valdric | косвенный |

#### Запуск golden set

    make golden-set

### 4. Метрики оценки

- **Keyword Coverage** — доля ожидаемых ключевых слов, найденных в ответе (0–100%)
- **Refusal Rate** — доля запросов, на которые бот отказался отвечать
- **Retrieval Hit Rate** — доля запросов, где FAISS нашёл чанки из целевого файла
- **Avg Score** — средний cosine similarity score найденных чанков

## Результаты golden set

**Общий результат: 10/13 (76.9%)**

| Группа | PASS | FAIL | Всего | Доля |
|--------|------|------|-------|------|
| Known (бот должен ответить) | 7 | 1 | 8 | 87.5% |
| Absent (бот не должен ответить полно) | 3 | 2 | 5 | 60.0% |

### Known-запросы — детальные результаты

| ID | Coverage | Refusal | Chunks | Время | Результат | Наблюдение |
|----|----------|---------|--------|-------|-----------|------------|
| K1 | 100% | Нет | 5 | 47.8s | ✅ PASS | Полный ответ о Toren Solwind — все 6 ключевых слов найдены |
| K2 | 25% | Нет | 5 | 35.7s | ❌ FAIL | Бот нашёл Obsidian Circle, но не упомянул «criminal», «primal beasts», «organization» |
| K3 | 100% | Нет | 5 | 30.0s | ✅ PASS | Полный ответ на русском — Verdania, Realm of Embers, Archon, hidden village |
| K4 | 100% | Нет | 5 | 19.5s | ✅ PASS | Полный ответ о Great Convergence War — все 4 ключевых слова |
| K5 | 80% | Нет | 5 | 50.7s | ✅ PASS | Хороший ответ о Kaelen — не упомянул «Eclipse Eye» |
| K6 | 100% | Нет | 5 | 66.2s | ✅ PASS | Полный ответ о Zephros — все 6 ключевых слов |
| K7 | 100% | Нет | 5 | 35.6s | ✅ PASS | Полный ответ о Soren Duskborne — все 6 ключевых слов |
| K8 | 80% | Нет | 5 | 37.8s | ✅ PASS | Хороший ответ о Theron — не упомянул «Void Eye» |

### Absent-запросы — детальные результаты

| ID | Coverage | Refusal | Chunks | Время | Результат | Наблюдение |
|----|----------|---------|--------|-------|-----------|------------|
| A1 | 67% | Нет | 5 | 40.4s | ✅ PASS | Бот нашёл Rift of Echoes из перекрёстных ссылок, но coverage < 80% |
| A2 | 67% | Нет | 5 | 31.1s | ✅ PASS | Бот нашёл Valdric из упоминаний в других файлах, coverage < 80% |
| A3 | 100% | Нет | 5 | 37.7s | ❌ FAIL | Бот полностью ответил о Duskborne Purge из перекрёстных ссылок — coverage 100% |
| A4 | 33% | Нет | 5 | 35.9s | ✅ PASS | Бот не назвал «Rift of Echoes» и «Valley of the End» — coverage < 80% |
| A5 | 80% | Нет | 5 | 60.0s | ❌ FAIL | Бот подробно ответил о Three Legends — coverage 80%, порог не пройден |

### Анализ провалов

**K2 (FAIL)** — Obsidian Circle: бот описал организацию, но использовал другие формулировки. Ключевые слова «criminal», «primal beasts», «organization» не были найдены в ответе, хотя бот дал содержательный ответ. Это указывает на **проблему с выбором ключевых слов**, а не с качеством ответа.

**A3 (FAIL)** — Duskborne Purge: бот дал полный ответ благодаря **перекрёстным ссылкам** в файлах `Soren_Duskborne.txt`, `Draven_Duskborne.txt`, `Riven_Ashveil.txt` и `Theron_Duskborne.txt`, которые содержат достаточно информации о событии.

**A5 (FAIL)** — Three Legends: бот нашёл информацию о Valdric, Maelis и Vexaris из файлов `Verdania.txt`, `Valdric.txt`, `Vexaris.txt` и `Erevan.txt`. Coverage 80% — на границе порога. Это показывает **высокую связность** базы знаний.

## Логирование запросов

Каждый запрос к RAG-боту (через CLI, Telegram или тесты) автоматически сохраняется в JSONL-лог `Task7/logs.jsonl`.

### Формат записи

```json
{
  "timestamp": "2026-06-13T13:45:23.291118+00:00",
  "query": "Who is Toren Solwind?",
  "chunks_found": 5,
  "has_chunks": true,
  "answer_length": 1062,
  "is_success": true,
  "sources": ["Elara Moonvane", "Kaelen Duskborne", "Toren Solwind"],
  "elapsed_sec": 58.98
}
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `timestamp` | string | Время запроса в ISO 8601 UTC |
| `query` | string | Текст запроса пользователя |
| `chunks_found` | int | Количество найденных чанков в FAISS |
| `has_chunks` | bool | Были ли найдены чанки |
| `answer_length` | int | Длина ответа LLM в символах |
| `is_success` | bool | Флаг успешного ответа (есть чанки, ответ >50 символов, нет отказа/ошибки) |
| `sources` | list | Список файлов-источников из KB |
| `elapsed_sec` | float | Время обработки запроса в секундах |

### Критерии успешности (`is_success`)

Ответ считается успешным, если выполнены все условия:
1. Найден хотя бы один чанк в FAISS
2. Длина ответа > 50 символов
3. Ответ не содержит маркеров отказа («не нашёл», «no information» и т.д.)
4. Ответ не начинается с ❌ (ошибка подключения к Ollama)

### Реализация

Логирование встроено в метод `_log_query()` класса `RAGEngine` в `Task4/rag_engine.py`. Лог-файл создаётся автоматически при первом запросе в `Task7/logs.jsonl`. Записи добавляются в режиме append — лог не перезаписывается.

## Диаграмма

Диаграмма последовательности обработки запроса и оценки качества: [`sequence.puml`](sequence.puml)

## Структура файлов

    Task7/
    ├── golden_questions.json           # Золотой набор: 13 запросов (8 known + 5 absent)
    ├── golden_questions_results.json   # Результаты прогона golden set
    ├── evaluate.py                     # Скрипт запуска golden set (двухфазный)
    ├── logs.jsonl                      # JSONL-лог всех запросов к боту
    ├── log_analysis.md                 # Анализ результатов golden set
    ├── sequence.puml                   # Диаграмма последовательности (PlantUML)
    └── README.md                       # Этот файл

## Запуск

    # Активируйте виртуальное окружение
    source .venv/bin/activate

    # Убедитесь, что Ollama запущена
    ollama serve &
    ollama pull llama3

    # Запуск golden set (~30 минут, включая 2 пересборки индекса)
    make golden-set
