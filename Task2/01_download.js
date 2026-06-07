const fetch = require("node-fetch");
const cheerio = require("cheerio");
const fs = require("fs");
const path = require("path");

// ============================================================
// Список персонажей — замените/дополните нужными именами.
// Имя должно совпадать с частью URL на вики (пробелы = _).
// Пример: "Kakashi_Hatake", "Naruto_Uzumaki", "Sasuke_Uchiha"
// ============================================================
const CHARACTER_NAMES = [
  "Kakashi_Hatake",
  "Naruto_Uzumaki",
  "Sasuke_Uchiha",
  "Sakura_Haruno",
  "Itachi_Uchiha",
  "Hinata_Hyūga",
  "Gaara",
  "Jiraiya",
  "Tsunade",
  "Orochimaru",
  "Minato_Namikaze",
  "Obito_Uchiha",
  "Madara_Uchiha",
  "Hashirama_Senju",
  "Tobirama_Senju",
  "Shikamaru_Nara",
  "Rock_Lee",
  "Neji_Hyūga",
  "Might_Guy",
  "Killer_B",
  "Pain_(character)",
  "Konan",
  "Deidara",
  "Sasori",
  "Hidan",
  "Kabuto_Yakushi",
  "Kushina_Uzumaki",
  "Boruto_Uzumaki",
  "Ino_Yamanaka",
  "Temari",
  "Nagato",
  "Shisui_Uchiha",
  "Hiruzen_Sarutobi",
  "Tenten",
  "Kaguya_Ōtsutsuki",
];

const BASE_URL = "https://naruto.fandom.com/wiki/";
const OUTPUT_DIR = path.join(__dirname, "raw_pages");
const DELAY_MS = 1000; // задержка между запросами, чтобы не нагружать сервер

/**
 * Скачивает HTML-страницу по URL и возвращает текстовое содержимое статьи.
 */
async function fetchCharacterText(name) {
  const url = `${BASE_URL}${encodeURIComponent(name)}`;
  console.log(`⏳  Загрузка: ${url}`);

  const response = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} для ${url}`);
  }

  const html = await response.text();
  const $ = cheerio.load(html);

  // Удаляем ненужные блоки: навигацию, инфобоксы, таблицы, скрипты, стили
  $(
    "script, style, noscript, .navbox, .infobox, .portable-infobox, " +
      ".toc, .mw-editsection, .reference, .references, .reflist, " +
      "#References, .navbox-container, .messagebox, .noprint, " +
      "table.wikitable, .quote, .mw-empty-elt, sup.reference"
  ).remove();

  // Основной контент статьи
  const content = $(".mw-parser-output");

  if (!content.length) {
    throw new Error(`Контент не найден на странице ${name}`);
  }

  // Извлекаем чистый текст
  let text = content.text();

  // Нормализуем пробелы и пустые строки
  text = text
    .replace(/\t/g, " ")
    .replace(/[ ]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return text;
}

/**
 * Пауза на заданное количество миллисекунд.
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Главная функция: последовательно скачивает все страницы.
 */
async function main() {
  // Создаём папку для результатов
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  console.log(`\n🔰  Начинаем загрузку ${CHARACTER_NAMES.length} персонажей...\n`);

  let success = 0;
  let failed = 0;

  for (const name of CHARACTER_NAMES) {
    try {
      const text = await fetchCharacterText(name);

      const filename = `${name}.txt`;
      const filepath = path.join(OUTPUT_DIR, filename);
      fs.writeFileSync(filepath, text, "utf-8");

      console.log(`✅  Сохранено: ${filename} (${text.length} символов)`);
      success++;
    } catch (err) {
      console.error(`❌  Ошибка для ${name}: ${err.message}`);
      failed++;
    }

    // Задержка между запросами
    await sleep(DELAY_MS);
  }

  console.log(
    `\n🏁  Готово! Успешно: ${success}, ошибок: ${failed}. ` +
      `Файлы сохранены в ${OUTPUT_DIR}\n`
  );
}

main();
