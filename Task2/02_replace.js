const fs = require("fs");
const path = require("path");

const RAW_DIR = path.join(__dirname, "raw");
const OUTPUT_DIR = path.join(__dirname, "knowledge_base");
const TERMS_MAP_PATH = path.join(__dirname, "terms_map.json");

/**
 * Загружает terms_map.json и строит плоский словарь замен { original → replacement }.
 * Сортирует ключи по длине (от длинных к коротким), чтобы длинные фразы
 * заменялись раньше коротких и не ломали друг друга.
 */
function buildReplacementMap() {
  const raw = JSON.parse(fs.readFileSync(TERMS_MAP_PATH, "utf-8"));

  // Объединяем все категории в один плоский словарь
  const flat = {};
  for (const category of Object.values(raw)) {
    for (const [original, replacement] of Object.entries(category)) {
      flat[original] = replacement;
    }
  }

  // Сортируем ключи по убыванию длины — длинные фразы заменяются первыми
  const sorted = Object.keys(flat).sort((a, b) => b.length - a.length);

  return { flat, sorted };
}

/**
 * Применяет все замены к тексту.
 * Использует регулярные выражения с границами слов для точного совпадения.
 */
function applyReplacements(text, flat, sortedKeys) {
  let result = text;

  for (const key of sortedKeys) {
    // Экранируем спецсимволы regex в ключе
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Используем границы слов для точного совпадения
    const regex = new RegExp(escaped, "g");
    result = result.replace(regex, flat[key]);
  }

  return result;
}

/**
 * Определяет новое имя файла, заменяя термины в имени файла.
 */
function replaceFilename(filename, flat, sortedKeys) {
  // Убираем расширение
  let name = filename.replace(/\.txt$/, "");

  // Заменяем подчёркивания на пробелы для поиска совпадений
  let readable = name.replace(/_/g, " ");

  // Применяем замены к читаемому имени
  for (const key of sortedKeys) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(escaped, "g");
    readable = readable.replace(regex, flat[key]);
  }

  // Возвращаем подчёркивания и расширение
  return readable.replace(/ /g, "_") + ".txt";
}

/**
 * Главная функция.
 */
function main() {
  // Проверяем наличие исходных данных
  if (!fs.existsSync(RAW_DIR)) {
    console.error(`❌  Папка ${RAW_DIR} не найдена. Сначала запустите 01_download.js`);
    process.exit(1);
  }

  if (!fs.existsSync(TERMS_MAP_PATH)) {
    console.error(`❌  Файл ${TERMS_MAP_PATH} не найден.`);
    process.exit(1);
  }

  // Создаём выходную папку
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // Строим словарь замен
  const { flat, sorted } = buildReplacementMap();
  console.log(`📖  Загружено ${sorted.length} терминов для замены.\n`);

  // Получаем список файлов
  const files = fs.readdirSync(RAW_DIR).filter((f) => f.endsWith(".txt"));
  console.log(`📂  Найдено ${files.length} файлов в ${RAW_DIR}\n`);

  let processed = 0;

  for (const file of files) {
    const inputPath = path.join(RAW_DIR, file);
    const text = fs.readFileSync(inputPath, "utf-8");

    // Заменяем термины в тексте
    const replacedText = applyReplacements(text, flat, sorted);

    // Заменяем термины в имени файла
    const newFilename = replaceFilename(file, flat, sorted);
    const outputPath = path.join(OUTPUT_DIR, newFilename);

    fs.writeFileSync(outputPath, replacedText, "utf-8");

    console.log(`✅  ${file} → ${newFilename}`);
    processed++;
  }

  console.log(
    `\n🏁  Готово! Обработано файлов: ${processed}. ` +
      `Результат в ${OUTPUT_DIR}\n`
  );
}

main();
