const fetch = require("node-fetch");
const cheerio = require("cheerio");
const fs = require("fs");
const path = require("path");

// ============================================================
// Список страниц для скачивания — замените/дополните нужными.
// Имя должно совпадать с частью URL на вики (пробелы = _).
// Пример: "Kakashi_Hatake", "Naruto_Uzumaki", "Konohagakure"
// ============================================================

// --- 20 персонажей ---
const CHARACTERS = [
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
  "Shikamaru_Nara",
  "Rock_Lee",
  "Neji_Hyūga",
  "Might_Guy",
  "Killer_B",
  "Kabuto_Yakushi",
  "Nagato",
];

// --- 15 мест и событий ---
const PLACES_AND_EVENTS = [
  "Konohagakure",
  "Sunagakure",
  "Kirigakure",
  "Kumogakure",
  "Iwagakure",
  "Amegakure",
  "Akatsuki",
  "Fourth_Shinobi_World_War",
  "Uchiha_Clan_Downfall",
  "Valley_of_the_End",
  "Mount_Myōboku",
  "Ryūchi_Cave",
  "Land_of_Fire",
];

const PAGE_NAMES = [...CHARACTERS, ...PLACES_AND_EVENTS];

// ============================================================
// Используем MediaWiki API вместо прямого доступа к страницам.
// Fandom защищён Cloudflare, который блокирует прямые HTTP-запросы
// (403 Forbidden). API-эндпоинт /api.php не проходит через
// Cloudflare и свободно отдаёт данные в формате JSON.
// ============================================================
const API_URL = "https://naruto.fandom.com/api.php";
const OUTPUT_DIR = path.join(__dirname, "raw");
const DELAY_MS = 1500; // задержка между запросами, чтобы не нагружать сервер

/**
 * Скачивает страницу через MediaWiki API (action=parse) и возвращает чистый текст.
 * API не блокирует запросы, в отличие от прямого доступа к HTML-страницам.
 */
async function fetchCharacterText(name) {
  const pageName = name.replace(/_/g, " ");
  const params = new URLSearchParams({
    action: "parse",
    page: pageName,
    prop: "text",
    format: "json",
    disablelimitreport: "true",
    disableeditsection: "true",
  });

  const url = `${API_URL}?${params}`;
  console.log(`⏳  Загрузка: ${pageName}`);

  const response = await fetch(url, {
    headers: {
      "User-Agent": "NarutoCharacterDownloader/1.0 (educational project)",
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} для ${pageName}`);
  }

  const data = await response.json();

  if (data.error) {
    throw new Error(`API ошибка: ${data.error.info}`);
  }

  const html = data.parse.text["*"];
  const $ = cheerio.load(html);

  // Удаляем ненужные блоки: навигацию, инфобоксы, таблицы, скрипты, стили
  $(
    "script, style, noscript, .navbox, .infobox, .portable-infobox, " +
      ".toc, .mw-editsection, .reference, .references, .reflist, " +
      "#References, .navbox-container, .messagebox, .noprint, " +
      "table.wikitable, .quote, .mw-empty-elt, sup.reference, " +
      ".thumb, figure, figcaption, .gallery, .wikia-gallery"
  ).remove();

  // Извлекаем чистый текст
  let text = $.root().text();

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

  console.log(`\n🔰  Начинаем загрузку ${PAGE_NAMES.length} страниц...\n`);

  let success = 0;
  let failed = 0;

  for (const name of PAGE_NAMES) {
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
