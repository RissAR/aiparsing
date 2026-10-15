# ТЗ №3: Модуль пошуку та збору конкурентів на Prom.ua (Discovery & Scraping)

## Мета
Реалізувати скрапер публічної пошукової видачі Prom.ua на основі стабільних селекторів `data-qaid` та сервіс пошуку конкурентів (`DiscoveryService`), який бере наші товари з БД `products`, знаходить за ними відповідні пропозиції на Prom.ua та зберігає їх у таблицю `competitor_offers`.

---

## Стек технологій та залежності
- **HTTP-клієнт:** `httpx>=0.27.0` (додати до `requirements.txt`)
- **HTML-парсинг:** `lxml>=5.0.0` (використовуємо `lxml.html`)
- **База даних:** SQLAlchemy 2.0+ (`Product`, `CompetitorOffer`)
- **CLI:** `argparse`

---

## Структура файлів до створення / модифікації
```text
/home/dofi/Dev/aiparsing/
├── requirements.txt                   # Додати httpx>=0.27.0
├── src/
│   └── services/
│       ├── prom_scraper.py            # HTTP-клієнт та парсер HTML-видачі Prom.ua
│       └── discovery_service.py       # Оркестратор пошуку для товарів з БД
└── scripts/
    └── discover_competitors.py        # CLI скрипт для запуску пошуку конкурентів
```

---

## Детальні вимоги до реалізації

### 1. Оновлення `requirements.txt`
Додати:
- `httpx>=0.27.0`

### 2. Скрапер Prom.ua `src/services/prom_scraper.py`
Створити клас `PromScraper`:
- **Конфігурація запиту:**
  - `User-Agent`: актуальний браузерний рядок (наприклад, `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36`).
  - `Accept-Language`: `uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7`.
  - Таймаут запиту: 10–15 секунд.
- **Метод `search(query: str, max_results: int = 5) -> list[dict]`:**
  - URL пошуку: `https://prom.ua/ua/search?search_term={quote(query)}`.
  - Парсинг HTML через `lxml.html.fromstring`.
  - Пошук блоків карток за XPath: `//*[@data-qaid="product_block"]`.
  - Для кожного блоку витягнути:
    1. **Назва товару:** `.//[@data-qaid="product_name"]` (текст).
    2. **Ціна:** `.//*[@data-qaid="product_price"]` — очистити від пробілів, нерозривних пробілів `\xa0` та знака `₴`, перетворити у `float`. Якщо ціну не вдалося розпарсити — пропускати.
    3. **Продавець:** `.//*[@data-qaid="company_name"]` (текст).
    4. **Наявність:** `.//*[@data-qaid="product_presence"]` (перевірка чи містить слова `наявності`, `відправки`, `в наявності` $\rightarrow$ `is_in_stock: bool`).
    5. **Посилання:** `.//*[@data-qaid="product_link"]/@href` або fallback `.//a[contains(@href, "/p")]/@href` $\rightarrow$ нормалізувати через `urllib.parse.urljoin("https://prom.ua", href)`.
    6. **Зображення:** `.//img/@src` (якщо є).
    7. **External ID:** витягнути з URL або data-атрибутів (наприклад, число після `-p` або параметр `?p=...`).
  - Повертати список словників `RawCompetitorOffer` розміром до `max_results`.
  - Безпечна обробка помилок (HTTP 4xx/5xx або таймаут не повинні викидати фатальний виняток, а повертати пустий список та логувати попередження).

### 3. Сервіс Discovery `src/services/discovery_service.py`
Створити клас `DiscoveryService`:
- **Метод `discover_for_product(db: Session, product: Product, max_offers: int = 5) -> int`:**
  - Формує пошуковий запит: якщо є валідний артикул `product.sku` (не порожній) — шукати за комбінацією `SKU` або за `title` (очищеним від зайвих символів).
  - Викликає `PromScraper.search(query, max_results=max_offers)`.
  - Для кожної знайденої пропозиції:
    - Перевіряє, чи вже існує запис у `competitor_offers` для даного `product_id` з таким самим `url`.
    - Якщо існує — оновлює `price`, `is_in_stock`, `scraped_at`.
    - Якщо новий — створює новий запис `CompetitorOffer`.
  - Зберігає зміни в БД (`db.commit()`).
  - Повертає кількість збережених/оновлених оферів.
- **Метод `discover_all(db: Session, limit_products: int = None, offers_per_product: int = 5, delay_seconds: float = 1.0)`:**
  - Проходить по активних товарах (`is_active == True`) з обмеженням `limit_products`.
  - Між запитами робить `time.sleep(delay_seconds)` для захисту від блокування.

### 4. CLI скрипт `scripts/discover_competitors.py`
Аргументи командного рядка:
- `--limit`: кількість товарів з каталогу для обробки (за замовчуванням `3`, для повного прогону можна передати більше).
- `--offers-per-product`: скільки конкурентів збирати для кожного товару (за замовчуванням `5`).
- `--delay`: пауза між товарами в секундах (за замовчуванням `1.5`).
- Інформативний вивід у консоль:
  ```text
  Запуск пошуку конкурентів на Prom.ua...
  Товарів до обробки: 3 | Оферів на товар: 5 | Затримка: 1.5s
  ------------------------------------------------------------
  [1/3] Наш товар: Павербанк Baseus Blade 100W 20000mAh Black (SKU: PPDGL-01)
        Пошуковий запит: 'PPDGL-01'
        -> Знайдено оферів: 5
        -> Збережено в базу (діапазон цін: 3299.0 - 4043.0 UAH)
  [2/3] ...
  ------------------------------------------------------------
  Пошук завершено. Всього зібрано пропозицій: 15
  ```

---

## Критерії приймання та верифікація (Verification)
1. Встановлено залежності:
   ```bash
   venv/bin/pip install -r requirements.txt
   ```
2. Запуск збору для перших 3-х товарів:
   ```bash
   venv/bin/python scripts/discover_competitors.py --limit 3 --offers-per-product 5 --delay 1.0
   ```
3. Перевірка збереження даних у БД:
   Виконати перевірочний однорядковий скрипт:
   ```bash
   venv/bin/python -c "from src.database.connection import SessionLocal; from src.database.models import CompetitorOffer; db = SessionLocal(); count = db.query(CompetitorOffer).count(); print(f'Total competitor offers in DB: {count}'); assert count > 0; db.close()"
   ```
   *Очікуваний результат:* у таблиці `competitor_offers` з'явилося > 0 записів з реальними цінами та посиланнями.

---

## Формат звіту після виконання
1. Список створених/модифікованих файлів.
2. Лог виконання команди `discover_competitors.py`.
3. Результат перевірки кількості записів у БД.
4. Єдина команда для git фіксації:
   `git add . && git commit -m "feat: implement Prom.ua scraper and competitor discovery service" && git push origin main`
