const fs = require("fs");
const path = require("path");

// ============================================================
// Конфигурация
// ============================================================
const CHUNKS_FILE = path.join(__dirname, "output", "chunks.jsonl");
const OUT_FILE = path.join(__dirname, "output", "embeddings.jsonl");

// Модель: intfloat/multilingual-e5-large (ONNX-квантизированная версия)
// Требует префикс "passage: " для индексируемых документов
const MODEL_NAME = "intfloat/multilingual-e5-large";
const PASSAGE_PREFIX = "passage: ";

// Размер батча — сколько чанков обрабатывать за раз
const BATCH_SIZE = 8;

/**
 * Средний пулинг (mean pooling) — усредняет токен-эмбеддинги
 * с учётом attention mask.
 */
function meanPooling(lastHiddenState, attentionMask) {
  const [batchSize, seqLen, hiddenSize] = lastHiddenState.dims;
  const result = [];

  for (let b = 0; b < batchSize; b++) {
    const embedding = new Float32Array(hiddenSize);
    let totalWeight = 0;

    for (let s = 0; s < seqLen; s++) {
      const mask = attentionMask.data[b * seqLen + s];
      if (mask === 0n || mask === 0) continue;
      totalWeight += 1;
      for (let h = 0; h < hiddenSize; h++) {
        embedding[h] += lastHiddenState.data[b * seqLen * hiddenSize + s * hiddenSize + h];
      }
    }

    if (totalWeight > 0) {
      for (let h = 0; h < hiddenSize; h++) {
        embedding[h] /= totalWeight;
      }
    }

    // L2-нормализация
    let norm = 0;
    for (let h = 0; h < hiddenSize; h++) {
      norm += embedding[h] * embedding[h];
    }
    norm = Math.sqrt(norm);
    if (norm > 0) {
      for (let h = 0; h < hiddenSize; h++) {
        embedding[h] /= norm;
      }
    }

    result.push(Array.from(embedding));
  }

  return result;
}

async function main() {
  if (!fs.existsSync(CHUNKS_FILE)) {
    console.error(`❌  Файл ${CHUNKS_FILE} не найден. Сначала запустите 01_chunking.js`);
    process.exit(1);
  }

  // Загружаем чанки
  const lines = fs.readFileSync(CHUNKS_FILE, "utf-8").trim().split("\n");
  const chunks = lines.map((line) => JSON.parse(line));
  console.log(`📂  Загружено ${chunks.length} чанков из ${CHUNKS_FILE}\n`);

  // Загружаем модель (feature-extraction pipeline)
  console.log(`🔄  Загрузка модели ${MODEL_NAME}...`);
  console.log("    (первый запуск скачает ~1.3 ГБ ONNX-модели)\n");

  const { pipeline } = await import("@xenova/transformers");

  const extractor = await pipeline("feature-extraction", MODEL_NAME, {
    quantized: false, // e5-large лучше работает без квантизации
  });

  console.log("✅  Модель загружена!\n");

  // Генерируем эмбеддинги батчами
  const outStream = fs.createWriteStream(OUT_FILE, { encoding: "utf-8" });
  let processed = 0;

  for (let i = 0; i < chunks.length; i += BATCH_SIZE) {
    const batch = chunks.slice(i, i + BATCH_SIZE);

    // Добавляем префикс "passage: " как требует модель e5
    const texts = batch.map((c) => PASSAGE_PREFIX + c.text);

    // Получаем эмбеддинги
    const output = await extractor(texts, {
      pooling: "mean",
      normalize: true,
    });

    // Записываем результаты
    for (let j = 0; j < batch.length; j++) {
      const embedding = Array.from(output[j].data);

      const record = {
        id: batch[j].id,
        embedding: embedding,
        metadata: batch[j].metadata,
        text: batch[j].text,
      };

      outStream.write(JSON.stringify(record) + "\n");
    }

    processed += batch.length;

    if (processed % 100 === 0 || processed === chunks.length) {
      const pct = ((processed / chunks.length) * 100).toFixed(1);
      console.log(`⏳  Обработано: ${processed}/${chunks.length} (${pct}%)`);
    }
  }

  outStream.end(() => {
    console.log(`\n🏁  Генерация эмбеддингов завершена!`);
    console.log(`📄  Файл сохранён: ${OUT_FILE}`);
    console.log(`📊  Всего записей: ${processed}\n`);
  });
}

main().catch((err) => {
  console.error("❌  Ошибка:", err.message);
  process.exit(1);
});
