const fs = require("fs");
const path = require("path");
const { RecursiveCharacterTextSplitter } = require("@langchain/textsplitters");

const KB_PATH = path.join(__dirname, "..", "Task2", "knowledge_base");
const OUT_FILE = path.join(__dirname, "output", "chunks.jsonl");

// ============================================================
// Параметры чанкинга:
// - chunkSize  = 800 символов ≈ 500–1000 токенов (100–300 слов)
// - chunkOverlap = 150 символов — перекрытие для сохранения контекста
// - Минимальный размер чанка: 30 символов (фильтруем заголовки-одиночки)
// ============================================================
const CHUNK_SIZE = 800;
const CHUNK_OVERLAP = 150;
const MIN_CHUNK_LENGTH = 30;

async function main() {
  if (!fs.existsSync(KB_PATH)) {
    console.error(`❌  Папка ${KB_PATH} не найдена. Сначала запустите Task2/02_replace.js`);
    process.exit(1);
  }

  const splitter = new RecursiveCharacterTextSplitter({
    chunkSize: CHUNK_SIZE,
    chunkOverlap: CHUNK_OVERLAP,
  });

  const files = fs.readdirSync(KB_PATH).filter((f) => f.endsWith(".txt")).sort();
  console.log(`📂  Найдено ${files.length} файлов в ${KB_PATH}\n`);

  // Создаём выходную папку
  const outDir = path.dirname(OUT_FILE);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  let chunkIdGlobal = 0;
  const outStream = fs.createWriteStream(OUT_FILE, { encoding: "utf-8" });

  for (const file of files) {
    const filePath = path.join(KB_PATH, file);
    const text = fs.readFileSync(filePath, "utf-8");

    const chunks = await splitter.splitText(text);

    let localId = 0;
    for (const chunk of chunks) {
      // Пропускаем слишком короткие чанки (заголовки-одиночки)
      if (chunk.trim().length < MIN_CHUNK_LENGTH) {
        continue;
      }

      // Находим позицию чанка в оригинальном тексте (char_offset)
      const charOffset = text.indexOf(chunk.slice(0, 50));

      const record = {
        id: chunkIdGlobal,
        text: chunk,
        metadata: {
          source: file,
          chunk_id: localId,
          char_offset: charOffset >= 0 ? charOffset : null,
          char_length: chunk.length,
          word_count: chunk.split(/\s+/).length,
        },
      };
      outStream.write(JSON.stringify(record, null, 0) + "\n");
      chunkIdGlobal++;
      localId++;
    }

    console.log(`✅  ${file}: ${localId} чанков`);
  }

  outStream.end(() => {
    console.log(`\n🏁  Чанкинг завершён. Создано чанков: ${chunkIdGlobal}`);
    console.log(`📄  Файл сохранён: ${OUT_FILE}\n`);
  });
}

main();
