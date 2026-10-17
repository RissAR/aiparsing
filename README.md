# ⚡ AI Repricer для Prom.ua

Автоматизована система моніторингу конкурентів на **Prom.ua**, гібридного AI-зіставлення товарів за допомогою **Google Gemini 2.5 Flash** та динамічного репрайсингу з жорстким захистом мінімальної маржинальності (Floor Price).

---

## 🎯 Основні можливості

1. **Імпорт та експорт каталогів (XML / YML):**
   - Парсинг стандартних фідів Prom.ua (`<yml_catalog>`, `<offer>`) із підтримкою автоматичного витягування собівартості (`<cost_price>` або `<param name="Собівартість|Закупка">`) та дефолтного розрахунку.
   - Генерація оновленого XML-фіду з новими цінами на льоту (`/api/export/feed.xml`) для прямого імпорту в кабінет продавця Prom.ua.
2. **Парсинг конкурентів з Prom.ua (`PromScraper` & `DiscoveryService`):**
   - Автоматичний пошук релевантних пропозицій на Prom.ua за назвою та артикулом (SKU).
   - Витягування актуальної ціни, назви магазину-продавця, статусу наявності, прямого URL та зображення з обробкою JSON-LD / HTML-розмітки.
3. **Гібридний рушій зіставлення (`MatchingEngine` + `GeminiMatcher`):**
   - **Rule-based фільтр:** миттєве відсіювання аксесуарів (чохлів, плівок до основних пристроїв), несумісних моделей чи критичних розбіжностей у характеристиках (потужність Вт, ємність мАг, довжина кабелю, роз'єми).
   - **Fuzzy Matching (`RapidFuzz`):** оцінка лексичної схожісті назв (`token_set_ratio`).
   - **AI-верифікація (`Google Gemini 2.5 Flash`):** глибокий семантичний аналіз спірних оферів із структурованим JSON-вердиктом (`is_same_product`, `confidence`, `reasoning` українською мовою).
4. **Динамічний репрайсинг із захистом маржі (`PricingEngine`):**
   - Розрахунок рекомендованої ціни відносно мінімальної активної ціни конкурента з кроком демпінгу `delta` (за замовчуванням `5.0 грн`).
   - Автоматичне підняття ціни (приріст прибутку), якщо магазин продає дешевше за ринок.
   - **Захист порогу рентабельності (`Floor Price`):** рекомендована ціна ніколи не опускається нижче `cost_price * (1 + min_margin_percent / 100)`.
5. **Веб-панель керування (FastAPI + PWA Dashboard):**
   - Живий індикатор прогресу покрокового автопілоту та панель сповіщень про помилки.
   - Дві робочі вкладки: **«Мій каталог і репрайсинг»** та **«Всі зібрані конкуренти з Prom.ua»** з миттєвим пошуком.
   - Детальне модальне вікно всіх оферів конкурентів для кожного товару з розгорнутим поясненням вердикту Gemini AI.
   - Підтримка встановлення як **PWA (Progressive Web App)** на робочий стіл.

---

## 🛠 Технічний стек

| Компонент | Технології |
| :--- | :--- |
| **Мова програмування** | Python 3.12+ |
| **Бекенд / REST API** | FastAPI, Uvicorn |
| **База даних та ORM** | SQLite, SQLAlchemy 2.0 |
| **Валідація та конфігурація** | Pydantic v2, `pydantic-settings`, `python-dotenv` |
| **Веб-скрапінг та XML** | `httpx`, `lxml` |
| **AI та нечіткий пошук** | Google GenAI SDK (`google-genai`, модель `gemini-2.5-flash`), `rapidfuzz` |
| **Фронтенд** | HTML5, Tailwind CSS, Vanilla JS, Lucide Icons, PWA (`manifest.json`, Service Worker) |

---

## 📂 Структура проєкту

```text
aiparsing/
├── data/
│   ├── samples/
│   │   └── prom_feed.xml            # Демонстраційний XML/YML фід каталогу товарів
│   └── app.db                       # Локальна база даних SQLite (ігнорується в Git)
├── scripts/
│   ├── init_db.py                   # Ініціалізація таблиць БД та тестового товару
│   ├── import_feed.py               # CLI-скрипт імпорту XML/YML фіду в БД
│   ├── discover_competitors.py      # CLI-скрипт пошуку та збору конкурентів на Prom.ua
│   ├── match_products.py            # CLI-скрипт запуску гібридного AI-матчингу
│   ├── calculate_prices.py          # CLI-скрипт розрахунку та застосування рекомендованих цін
│   └── update_images.py             # Скрипт оновлення валідних URL зображень товарів
├── src/
│   ├── api/
│   │   └── app.py                   # FastAPI додаток, REST API маршрути та роздача статики
│   ├── database/
│   │   ├── connection.py            # Налаштування Engine та сесій SQLAlchemy
│   │   └── models.py                # Моделі: Product, CompetitorOffer, ProductMatch, PriceRecommendation
│   ├── services/
│   │   ├── feed_importer.py         # Парсинг та Upsert товарних фідів XML/YML
│   │   ├── feed_exporter.py         # Генерація оновленого XML-фіду з актуальними цінами
│   │   ├── prom_scraper.py          # HTTP-клієнт та парсер пошукової видачі Prom.ua
│   │   ├── discovery_service.py     # Оркестратор збору пропозицій конкурентів
│   │   ├── ai_matcher.py            # Інтеграція з Google Gemini 2.5 Flash API
│   │   ├── matching_engine.py       # Комбінований пайплайн зіставлення (Rules + Fuzzy + AI)
│   │   └── pricing_engine.py        # Алгоритм динамічного ціноутворення та захисту маржі
│   ├── web/
│   │   └── static/
│   │       ├── index.html           # Інтерактивний клієнтський дашборд
│   │       ├── manifest.json        # Конфігурація PWA
│   │       └── sw.js                # Service Worker
│   └── config.py                    # Налаштування середовища через Pydantic Settings
├── .env.example                     # Шаблон змінних середовища (без секретів)
├── .gitignore                       # Правила виключення секретів (.env) та локальної БД (*.db)
├── requirements.txt                 # Залежності Python
└── run_app.py                       # Точка входу для запуску веб-сервера
```

---

## 🚀 Швидкий старт

### 1. Клонування та налаштування віртуального середовища

```bash
git clone https://github.com/RissAR/aiparsing.git
cd aiparsing

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Налаштування змінних середовища

Скопіюйте шаблон `.env.example` у файл `.env` та вкажіть ваш ключ Google Gemini API:

```bash
cp .env.example .env
```

Вміст `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```
*(Якщо `GEMINI_API_KEY` не заданий, система автоматично працюватиме в безпечному режимі на базі правил та нечіткого порівняння `RapidFuzz`).*

### 3. Ініціалізація бази даних та імпорт каталогу

```bash
# Створення таблиць SQLite
venv/bin/python scripts/init_db.py

# Імпорт товарів із XML-фіду
venv/bin/python scripts/import_feed.py --file data/samples/prom_feed.xml
```

### 4. Запуск веб-панелі керування

```bash
venv/bin/python run_app.py
```

Після запуску відкрийте у браузері: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 💻 Використання через CLI

Усі етапи пайплайну можна запускати окремо з термінала:

```bash
# 1. Збір пропозицій конкурентів з Prom.ua (наприклад, для 13 товарів по 5 оферів)
venv/bin/python scripts/discover_competitors.py --limit 13 --offers-per-product 5 --delay 1.0

# 2. Гібридне зіставлення товарів (Rules + RapidFuzz + Gemini 2.5 Flash)
venv/bin/python scripts/match_products.py --link-existing

# 3. Розрахунок рекомендованих цін (із кроком -5 грн від конкурента)
venv/bin/python scripts/calculate_prices.py --delta 5.0

# 4. Розрахунок із миттєвим застосуванням нових цін у каталог
venv/bin/python scripts/calculate_prices.py --delta 5.0 --apply
```

---

## 🔌 Основні маршрути REST API

- `GET /api/stats` — агрегована статистика (кількість активних товарів, оферів конкурентів, схвалених AI-збігів, потенційний приріст прибутку).
- `GET /api/products` — повний список товарів каталогу з прив'язаними конкурентами, вердиктами AI та поточними ціновими рекомендаціями.
- `GET /api/competitor-offers` — повний перелік усіх зібраних пропозицій конкурентів на Prom.ua.
- `POST /api/actions/run-all` — запуск повного циклу автопілоту (`Discovery` $\rightarrow$ `Matching` $\rightarrow$ `Repricing`).
- `POST /api/actions/discover` — запуск скрапінгу конкурентів Prom.ua.
- `POST /api/actions/match` — запуск AI-зіставлення оферів.
- `POST /api/actions/reprice` — запуск перерахунку рекомендованих цін.
- `POST /api/actions/apply/{product_id}` — застосування рекомендованої ціни для конкретного товару.
- `POST /api/actions/apply-all` — масове застосування всіх активних цінових рекомендацій.
- `GET /api/export/feed.xml` — завантаження готового YML/XML фіду з оновленими цінами для Prom.ua.

---

## 🔒 Безпека даних

- Файл `.env` із реальними ключами API та локальна база даних `data/*.db` додані до `.gitignore` і не відстежуються системою контролю версій Git.
- Для конфігурації використовується шаблон `.env.example`.
