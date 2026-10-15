# ТЗ №6: PWA Дашборд модерації (UI), Панель управління та Експорт оновленого фіду Prom.ua

## Мета
Створити повноцінний автономний клієнтський додаток із веб-інтерфейсом (PWA SPA у стилі початкового макету), панеллю кнопок для запуску процесів парсингу, AI-аналізу та репрайсингу, інтерактивною таблицею модерації цін і автоматичним генератором оновленого XML-фіду для Prom.ua.

---

## Стек технологій та залежності
- **Бекенд веб-сервер:** `fastapi>=0.110.0`, `uvicorn>=0.28.0` (додати до `requirements.txt`)
- **База даних:** SQLAlchemy 2.0+ (використовуємо існуючі моделі)
- **Фронтенд:** Сучасний Single-Page Application (HTML5 + Tailwind CSS CDN + Lucide Icons + PWA Manifest)
- **Експорт даних:** `lxml.etree` для генерації валідного Prom.ua YML/XML фіду

---

## Структура файлів до створення / модифікації
```text
/home/dofi/Dev/aiparsing/
├── requirements.txt                   # Додати fastapi>=0.110.0, uvicorn>=0.28.0
├── run_app.py                         # Головний запуск додатку: python run_app.py
├── src/
│   ├── services/
│   │   └── feed_exporter.py           # Сервіс генерації актуального XML/YML фіду для Prom.ua
│   ├── api/
│   │   ├── __init__.py
│   │   └── app.py                     # FastAPI сервер з REST ендпоінтами управління
│   └── web/
│       └── static/
│           ├── index.html             # Головний UI дашборд (темна тема, таблиця, кнопки)
│           ├── manifest.json          # PWA маніфест (назва, іконки, standalone режим)
│           └── sw.js                  # Service Worker для роботи PWA
```

---

## Детальні вимоги до реалізації

### 1. Оновлення `requirements.txt`
Додати:
- `fastapi>=0.110.0`
- `uvicorn>=0.28.0`

---

### 2. Сервіс експорту фіду `src/services/feed_exporter.py`
Створити клас `FeedExporter`:
- **Метод `generate_xml(db: Session) -> str`:**
  - Отримує всі активні товари `Product.is_active == True`.
  - Формує валідний XML за стандартом YML / Prom.ua:
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <yml_catalog date="...">
      <shop>
        <name>Мій Магазин (AI Repriced)</name>
        <currencies>
          <currency id="UAH" rate="1"/>
        </currencies>
        <categories>
          <category id="1">Електроніка та аксесуари</category>
        </categories>
        <offers>
          <!-- Для кожного товару з актуальною current_price -->
          <offer id="..." available="true">
            <name>...</name>
            <vendorCode>SKU</vendorCode>
            <price>АКТУАЛЬНА_ЦІНА</price>
            <currencyId>UAH</currencyId>
            <categoryId>1</categoryId>
            <picture>...</picture>
          </offer>
        </offers>
      </shop>
    </yml_catalog>
    ```
  - Повертає XML у вигляді рядка UTF-8.
- **Метод `save_to_file(db: Session, filepath: str = "data/exports/prom_updated_feed.xml") -> str`:**
  - Зберігає згенерований XML у файл та повертає шлях.

---

### 3. FastAPI бекенд `src/api/app.py`
Створити додаток `app = FastAPI(title="AI Repricer for Prom.ua")`:
- Підключити роздачу статичних файлів із папки `src/web/static` на кореневий маршрут `/`.
- **REST API ендпоінти:**
  1. `GET /api/stats`:
     - Повертає зведену статистику: `total_products`, `total_offers`, `approved_matches`, `applied_recommendations`, `potential_profit_boost` (сума додаткового прибутку за недооціненими товарами).
  2. `GET /api/products`:
     - Повертає список товарів з БД.
     - Для кожного товару включає:
       - Поля товару (`id`, `sku`, `title`, `current_price`, `cost_price`, `image_url`).
       - Список пов'язаних `competitors` (назва магазину, ціна, наявність, url).
       - Статус матчингу (`confidence_score`, `match_method`, `status`, `ai_reasoning`).
       - Рекомендацію ціни (`recommended_price`, `min_market_price`, `status`).
  3. `POST /api/actions/run-all`:
     - Запускає повний цикл (Discovery $\rightarrow$ AI Match $\rightarrow$ Repricing).
     - Повертає статус виконання.
  4. `POST /api/actions/discover`: запуск пошуку оферів на Prom.ua.
  5. `POST /api/actions/match`: запуск AI-зіставлення через Gemini.
  6. `POST /api/actions/reprice`: запуск розрахунку рекомендованих цін.
  7. `POST /api/actions/apply/{product_id}`: застосування рекомендованої ціни для конкретного товару.
  8. `POST /api/actions/apply-all`: застосування всіх схвалених рекомендацій до каталогу.
  9. `GET /api/export/feed.xml`:
     - Повертає оновлений XML-фід із заголовком `Content-Type: application/xml`. Клієнт може відкрити цей URL або вставити безпосередньо в кабінет Prom.ua.

---

### 4. PWA Клієнтський дашборд `src/web/static/`

#### `index.html`:
Створити естетичний, високоякісний адаптивний SPA-інтерфейс:
- **Дизайн та стилі:**
  - Темна сучасна палітра (як на початковому референсі: глибокий темно-синій/slate фон `#0b1120`, градієнтні акценти синього, фіолетового та бірюзового, заокруглені картки з тонкими рамками).
  - Підключення Tailwind CSS через CDN та іконки Lucide (або Heroicons SVG).
- **Шапка (Header):**
  - Логотип і назва: `AI Repricer // Prom.ua Intelligence`.
  - Бейджі статусу: `БД: Підключено` | `AI: Gemini 2.5 Flash Активний`.
- **Панель швидких дій (Action Bar):**
  - Кнопка з градієнтом: `[ 🚀 Запустити повний автопілот ]` (викликає `/api/actions/run-all` з індикатором завантаження/спінером).
  - Допоміжні кнопки: `[ 🔍 Зібрати Prom ]`, `[ 🤖 AI-Матчинг ]`, `[ ⚡ Перерахувати ціни ]`, `[ ✓ Застосувати всі ціни ]`.
  - Кнопка завантаження: `[ 📥 Завантажити XML для Prom.ua ]` (відкриває або скачує `/api/export/feed.xml`).
- **Блок ключових метрик (4 плашки зі скріншота):**
  1. *Каталог товарів* (кількість активних товарів).
  2. *Конкурентні пропозиції* (знайдено цін на Prom).
  3. *AI Аналіз* (кількість успішно схвалених зв'язок).
  4. *Приріст маржі* (сума збереженого прибутку у ₴).
- **Інтерактивна таблиця моніторингу цін:**
  - Поля таблиці:
    - **Товар:** Зображення, Назва, SKU (артикул).
    - **Собівартість & Поточна ціна:** закупка, поріг маржі, поточна ціна в магазині.
    - **Ціни конкурентів (Prom.ua):** картки зі знайденими магазинами («PixelCase», «Ціновал» тощо), їхніми цінами та клікабельними посиланнями на сторінку товару.
    - **Вердикт AI:** бейдж із відсотком впевненості (зелений 98% exact, синій 95% gemini, червоний rejected) та підказка з детальним поясненням `ai_reasoning`.
    - **Рекомендована ціна:** нове значення ціни з кольоровою позначкою (зелена стрілочка вгору `▲ +620 грн` або вниз).
    - **Дія:** Кнопка `[ Застосувати ]` (відправляє POST-запит і миттєво оновлює рядок без перезавантаження сторінки).

#### `manifest.json`:
- `name`: "AI Repricer Prom.ua"
- `short_name`: "Repricer"
- `start_url`: "/"
- `display`: "standalone"
- `background_color`: "#0b1120"
- `theme_color`: "#1e293b"

#### `sw.js`:
- Базовий Service Worker для кешування статичних ресурсів та забезпечення PWA-стандарту.

---

### 5. Головний запуск клієнтського додатку `run_app.py`
Створити скрипт запуску в корені проєкту:
- Використовує `uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000, reload=True)`.
- При запуску виводить красиве вітальне повідомлення:
  ```text
  ============================================================
  🚀 AI Repricer для Prom.ua успішно запущено!
  👉 Відкрийте у браузері: http://127.0.0.1:8000
  📱 Підтримується встановлення як PWA додаток на робочий стіл
  ============================================================
  ```

---

## Критерії приймання та верифікація (Verification)
1. Встановлення залежностей:
   ```bash
   venv/bin/pip install -r requirements.txt
   ```
2. Тестова перевірка генерації XML-фіду:
   ```bash
   venv/bin/python -c "from src.database.connection import SessionLocal; from src.services.feed_exporter import FeedExporter; db = SessionLocal(); xml = FeedExporter.generate_xml(db); print(f'XML Length: {len(xml)}, Valid tags: {\"<yml_catalog>\" in xml and \"<offers>\" in xml}'); assert len(xml) > 0; db.close()"
   ```
3. Тестова перевірка запуску API:
   Запустити фоновий сервер або перевірити імпорт та маршрути додатку:
   ```bash
   venv/bin/python -c "from src.api.app import app; print('FastAPI app routes:', [r.path for r in app.routes])"
   ```
   *Очікуваний результат:* наявні маршрути `/`, `/api/stats`, `/api/products`, `/api/actions/run-all`, `/api/export/feed.xml`.

---

## Формат звіту після виконання
1. Список створених/модифікованих файлів.
2. Результат верифікації генератора XML та маршрутів FastAPI.
3. Єдина команда для git фіксації:
   `git add . && git commit -m "feat: implement PWA web dashboard, control center API, and Prom.ua feed exporter" && git push origin main`
