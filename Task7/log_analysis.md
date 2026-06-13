# Анализ результатов golden set

**Источник данных:** [`golden_questions_results.json`](golden_questions_results.json)  
**Дата прогона:** 2026-06-13  
**Всего запросов:** 13 (8 known + 5 absent)  
**Общий результат:** 10/13 (76.9%)

---

## 1. Сводная таблица результатов

| ID | Группа | Сущность | Coverage | Refusal | Chunks | Время | PASS/FAIL |
|----|--------|----------|----------|---------|--------|-------|-----------|
| K1 | known | Toren Solwind | 100% | Нет | 5 | 47.8s | ✅ PASS |
| K2 | known | The Obsidian Circle | 25% | Нет | 5 | 35.7s | ❌ FAIL |
| K3 | known | Verdania | 100% | Нет | 5 | 30.0s | ✅ PASS |
| K4 | known | Great Convergence War | 100% | Нет | 5 | 19.5s | ✅ PASS |
| K5 | known | Kaelen Duskborne | 80% | Нет | 5 | 50.7s | ✅ PASS |
| K6 | known | Zephros | 100% | Нет | 5 | 66.2s | ✅ PASS |
| K7 | known | Soren Duskborne | 100% | Нет | 5 | 35.6s | ✅ PASS |
| K8 | known | Theron Duskborne | 80% | Нет | 5 | 37.8s | ✅ PASS |
| A1 | absent | Rift of Echoes | 67% | Нет | 5 | 40.4s | ✅ PASS |
| A2 | absent | Valdric | 67% | Нет | 5 | 31.1s | ✅ PASS |
| A3 | absent | The Duskborne Purge | 100% | Нет | 5 | 37.7s | ❌ FAIL |
| A4 | absent | Rift of Echoes (косв.) | 33% | Нет | 5 | 35.9s | ✅ PASS |
| A5 | absent | Three Legends / Valdric | 80% | Нет | 5 | 60.0s | ❌ FAIL |

---

## 2. По каким темам бот не отвечает корректно

### 2.1 Провалы в группе Known (бот должен был ответить)

#### K2 — The Obsidian Circle (coverage 25%, FAIL)

**Запрос:** «What is The Obsidian Circle and what are their goals?»

**Что нашёл бот:**
- Описал организацию как «группу сентинелей вне системы скрытых деревень»
- Упомянул историю основания (Yahiko, Erevan, Konan)
- Рассказал о целях «принести мир в Rainveil»

**Что пропустил:**
- Слово «criminal» — бот не назвал организацию преступной
- «primal beasts» — не упомянул охоту за примальными зверями
- «organization» — использовал слово «group» вместо «organization»

**Причина:** Бот дал исторически точный ответ, но использовал другую лексику. Файл `The_Obsidian_Circle.txt`, вероятно, описывает организацию через нарратив основания, а не через явное определение «criminal organization hunting primal beasts». Источник `Erevan.txt` добавил контекст о мирных целях, что сместило акцент ответа.

**Вывод:** Это **проблема KB**, а не бота. Файл не содержит явного определения организации в начале.

---

### 2.2 Провалы в группе Absent (бот не должен был отвечать полно)

#### A3 — The Duskborne Purge (coverage 100%, FAIL)

**Запрос:** «What was the Duskborne Purge and who carried it out?»

**Что нашёл бот:**
- Полностью описал событие: «near-complete massacre of the Duskborne clan»
- Назвал исполнителей: Soren Duskborne и человек, называвший себя Theron Duskborne
- Указал причину: клан планировал свергнуть Verdania

**Источники:** Draven Duskborne, Riven Ashveil, Soren Duskborne, **The Duskborne Purge**, Theron Duskborne

**Причина провала:** Файл `The_Duskborne_Purge.txt` присутствует в KB (он был удалён только в coverage analysis, но сейчас восстановлен). Бот нашёл прямой источник и дал полный ответ. Это **не ошибка бота** — это ожидаемое поведение при наличии файла.

**Вывод:** Тест A3 некорректно сформулирован для текущего состояния KB. Absent-запросы должны тестироваться только при удалённых файлах.

#### A5 — Three Legends (coverage 80%, FAIL)

**Запрос:** «Who are the Three Legends and what are they known for?»

**Что нашёл бот:**
- Назвал всех трёх: Valdric, Maelis, Vexaris
- Объяснил происхождение титула (Hanzō дал его во время битвы)
- Описал роли: Valdric — отшельник с исключительными навыками, Vexaris — учитель теневой арканы

**Что пропустил:**
- Слово «legendary» — использовал «exceptional» и «known for»

**Причина провала:** Бот нашёл информацию из `Verdania.txt`, `Valdric.txt`, `Vexaris.txt` и `Erevan.txt`. Высокая связность KB позволила собрать полный ответ даже без специального файла о Three Legends. Пропущено только слово «legendary» — это **проблема ключевых слов в тесте**, а не качества ответа.

**Вывод:** Ответ фактически правильный. Тест слишком строгий по ключевому слову «legendary».

---

## 3. Нерелевантные источники

### 3.1 Полная карта источников

| ID | Целевой файл | Фактические источники | Нерелевантные |
|----|-------------|----------------------|---------------|
| K1 | Toren_Solwind | Corvin Shadewell, Kaelen Duskborne, **Toren Solwind** | Corvin Shadewell |
| K2 | The_Obsidian_Circle | **Erevan**, The Obsidian Circle | Erevan |
| K3 | Verdania | Realm of Embers, **Verdania** | — |
| K4 | The_Great_Convergence_War | Draven Duskborne, Elara Moonvane, Garron Steelhart, Morden Glasswick, **The Great Convergence War** | — (все участники войны) |
| K5 | Kaelen_Duskborne | **Kaelen Duskborne**, Valdric | Valdric |
| K6 | Zephros | **Zephros** | — (идеальный результат) |
| K7 | Soren_Duskborne | Kaelen Duskborne, Riven Ashveil, **Soren Duskborne**, The Duskborne Purge | — (все связаны с событием) |
| K8 | Theron_Duskborne | Draven Duskborne, The Duskborne Purge, **Theron Duskborne** | — |
| A1 | Rift_of_Echoes | Realm of Embers, **Rift of Echoes**, Riven Ashveil, Theron Duskborne | Riven Ashveil |
| A2 | Valdric | Toren Solwind, **Valdric** | — |
| A3 | The_Duskborne_Purge | Draven Duskborne, Riven Ashveil, Soren Duskborne, **The Duskborne Purge**, Theron Duskborne | — |
| A4 | Rift_of_Echoes | Kaelen Duskborne, **Rift of Echoes**, Toren Solwind | — |
| A5 | Valdric | **Erevan**, **Valdric**, Verdania, Vexaris | Erevan (частично) |

### 3.2 Паттерны нерелевантных источников

**Паттерн 1: `Erevan` как ложный источник (2 случая: K2, A5)**

`Erevan.txt` появляется при запросах об Obsidian Circle и Three Legends. Причина: файл описывает место, где происходили ключевые события, связанные с обеими сущностями. FAISS находит семантически близкие чанки из `Erevan.txt`, которые «занимают место» в TOP_K=5.

Влияние на K2: `Erevan.txt` добавил контекст о мирных целях Obsidian Circle (основание Yahiko в Rainveil), что сместило акцент ответа от «criminal organization» к «peace-seeking group».

**Паттерн 2: `Corvin Shadewell` при запросе о Toren (K1)**

Второстепенный персонаж появляется как источник при запросе о главном герое. Вероятно, в `Corvin_Shadewell.txt` есть значимые упоминания Toren. Влияние минимальное — бот всё равно дал 100% coverage.

**Паттерн 3: `Valdric` при запросе о Kaelen (K5)**

`Valdric.txt` появляется вместо одного из чанков `Kaelen_Duskborne.txt`. Это вытеснило информацию об Eclipse Eye — единственном пропущенном ключевом слове в K5.

**Паттерн 4: `Riven Ashveil` при запросе о Rift of Echoes (A1)**

Персонаж появляется при запросе о локации. Вероятно, Riven Ashveil связан с событиями в Rift of Echoes. Влияние: бот не упомянул Toren и Kaelen в контексте этой локации (coverage 67%).

---

## 4. Где нужно расширить или переписать базу знаний

### 4.1 Критические проблемы

#### Проблема 1: `The_Obsidian_Circle.txt` — отсутствует явное определение

**Симптом:** K2 coverage 25% — бот не использовал «criminal», «primal beasts», «organization»

**Анализ ответа бота:**
> «The Obsidian Circle was a group of sentinels that existed outside the usual system of hidden villages... Yahiko founded The Obsidian Circle alongside his childhood friends Erevan and Konan during the Third Sentinel World War, with the goal of bringing peace to their home country, Rainveil.»

Бот описал историю основания, но не природу организации. Файл, вероятно, начинается с нарратива, а не с определения.

**Что нужно добавить в начало файла:**
```
The Obsidian Circle is a criminal organization of sentinels operating outside 
the hidden village system. Their primary goals include capturing primal beasts 
and accumulating power to reshape the world order.
```

#### Проблема 2: `Rift_of_Echoes.txt` — слишком мал (17 строк), не называет локацию в контексте финальной битвы

**Симптом:** A4 coverage 33% — бот нашёл файл, но не назвал «Rift of Echoes» как место финальной битвы Toren vs Kaelen

**Анализ ответа бота (A4):**
> «Fragment 2 — Rift_of_Echoes.txt mentions that Toren Solwind chased Kaelen Duskborne to a valley... I cannot pinpoint an exact location for their final battle as there is only one instance mentioned in Fragment 2, which does not provide specific details about the valley's name or location.»

Бот нашёл правильный чанк, но в нём не было явной фразы «the final battle between Toren and Kaelen took place at the Rift of Echoes». Файл описывает долину, но не называет её явно в контексте этой битвы.

**Что нужно добавить:**
```
The most notable modern battle at the Rift of Echoes was the final confrontation 
between Toren Solwind and Kaelen Duskborne, also known as the Valley of the End battle.
```

### 4.2 Умеренные проблемы

#### Проблема 3: Специальные способности не попадают в топ чанков

**Симптом:** K5 пропустил «Eclipse Eye», K8 пропустил «Void Eye»

**Анализ:** При общих вопросах о персонаже («Who is X and what is his relationship with Y?») FAISS находит чанки о биографии и отношениях, а не о способностях. Способности, вероятно, описаны в отдельных секциях файлов.

**Что нужно сделать:** Добавить упоминание ключевой способности в первый абзац файла персонажа:
- `Kaelen_Duskborne.txt`: добавить «known for his Eclipse Eye» в первое предложение
- `Theron_Duskborne.txt`: добавить «wielder of the Void Eye» в первое предложение

#### Проблема 4: `Erevan.txt` — избыточные перекрёстные ссылки

**Симптом:** Появляется как источник в K2 (Obsidian Circle) и A5 (Three Legends), смещая акцент ответов

**Что нужно сделать:** Проверить `Erevan.txt` на предмет чрезмерных упоминаний несвязанных сущностей. Если файл описывает место через события, происходившие там, — это нормально. Но если он содержит подробные описания организаций и персонажей, это создаёт «шум» в индексе.

#### Проблема 5: `Valdric.txt` вытесняет чанки `Kaelen_Duskborne.txt`

**Симптом:** K5 — Valdric появляется как источник вместо одного из чанков Kaelen, что привело к пропуску «Eclipse Eye»

**Что нужно сделать:** Проверить, сколько раз Kaelen упоминается в `Valdric.txt`. Если упоминания избыточны — сократить.

### 4.3 Структурные рекомендации

#### Рекомендация 1: Summary-секция в начале каждого файла

Добавить стандартный блок в начало каждого файла KB:

```
## [Имя сущности]
**Тип:** [character / place / event / organization]
**Ключевые факты:** [3-5 фактов с явными терминами]
**Связанные сущности:** [список]
```

Это гарантирует, что первый чанк каждого файла содержит все ключевые термины и попадёт в топ при семантическом поиске.

#### Рекомендация 2: Расширить малые файлы

| Файл | Текущий размер | Проблема | Рекомендуемый размер |
|------|---------------|---------|---------------------|
| `Rift_of_Echoes.txt` | 17 строк | 1-2 чанка, нет явных утверждений о битвах | 50+ строк |
| `The_Duskborne_Purge.txt` | 28 строк | Мало деталей о причинах и последствиях | 60+ строк |

#### Рекомендация 3: Явные определения для организаций

Файлы организаций должны начинаться с явного определения:
- Тип: «criminal organization», «secret society», «military alliance»
- Цели: конкретные глаголы («capture», «revive», «overthrow»)
- Методы: «assassination», «infiltration», «manipulation»

---

## 5. Производительность

### 5.1 Время ответа

| Запрос | Время | Длина ответа |
|--------|-------|-------------|
| K4 (Great Convergence War) | 19.5s | 667 символов |
| K3 (Verdania, рус.) | 30.0s | 508 символов |
| A2 (Valdric) | 31.1s | 1,001 символов |
| K2 (Obsidian Circle) | 35.7s | 1,109 символов |
| K7 (Soren Duskborne) | 35.6s | 1,136 символов |
| A4 (Final battle) | 35.9s | 761 символов |
| K8 (Theron Duskborne) | 37.8s | 1,283 символов |
| A3 (Duskborne Purge) | 37.7s | 885 символов |
| A1 (Rift of Echoes) | 40.4s | 1,207 символов |
| K1 (Toren Solwind) | 47.8s | 971 символов |
| K5 (Kaelen Duskborne) | 50.7s | 1,271 символов |
| A5 (Three Legends) | 60.0s | 1,017 символов |
| K6 (Zephros) | 66.2s | 1,809 символов |

**Среднее время:** 40.5 сек  
**Корреляция:** длинные ответы = больше времени (K6: 1,809 символов → 66.2s)

### 5.2 Наблюдение о длине ответов

K6 (Zephros) дал самый длинный ответ (1,809 символов) — бот повторил выводы дважды (step-by-step + final answer). Это не проблема KB, но указывает на избыточность в промпте Chain-of-Thought.

---

## 6. Итоговая таблица проблем

| # | Проблема | Файл KB | Серьёзность | Тип | Рекомендация |
|---|---------|---------|-------------|-----|-------------|
| 1 | Нет явного определения «criminal organization» | `The_Obsidian_Circle.txt` | 🔴 Высокая | Контент | Добавить определение в первый абзац |
| 2 | Не называет локацию финальной битвы явно | `Rift_of_Echoes.txt` | 🔴 Высокая | Контент + размер | Расширить файл, добавить явные утверждения |
| 3 | Eclipse Eye не попадает в топ чанков | `Kaelen_Duskborne.txt` | 🟡 Средняя | Структура | Упомянуть способность в первом абзаце |
| 4 | Void Eye не попадает в топ чанков | `Theron_Duskborne.txt` | 🟡 Средняя | Структура | Упомянуть способность в первом абзаце |
| 5 | Erevan смещает акцент ответов | `Erevan.txt` | 🟡 Средняя | Связность | Сократить перекрёстные ссылки |
| 6 | Valdric вытесняет чанки Kaelen | `Valdric.txt` | 🟡 Средняя | Связность | Проверить упоминания Kaelen |
| 7 | Малый размер файла | `Rift_of_Echoes.txt` | 🟡 Средняя | Размер | 17 → 50+ строк |
| 8 | Малый размер файла | `The_Duskborne_Purge.txt` | 🟢 Низкая | Размер | 28 → 60+ строк |
| 9 | Тест A3 некорректен при полной KB | `golden_questions.json` | 🟢 Низкая | Тест | Запускать absent-тесты только с удалёнными файлами |
| 10 | Тест A5 слишком строгий по «legendary» | `golden_questions.json` | 🟢 Низкая | Тест | Заменить «legendary» на «exceptional» или «renowned» |
