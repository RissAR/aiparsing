# ТЗ №1: Ініціалізація проєкту та Схема даних (Data Layer)

## Мета
Створити базовий каркас Python-проєкту та реляційну схему даних на SQLite через SQLAlchemy для збереження власних товарів, пропозицій конкурентів з Prom.ua, результатів матчингу та історії розрахованих цін.

---

## Стек технологій
- **Мова:** Python 3.11+
- **ORM / База даних:** SQLAlchemy 2.0+ / SQLite (`data/app.db`)
- **Валідація / Типізація:** Pydantic v2
- **Управління оточенням:** `requirements.txt` + `venv`

---

## Структура файлів до створення
```text
/home/dofi/Dev/aiparsing/
├── .gitignore
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py
│   └── database/
│       ├── __init__.py
│       ├── connection.py
│       └── models.py
└── scripts/
    └── init_db.py
```

---

## Вимоги до реалізації

### 1. `requirements.txt`
Зафіксувати мінімально необхідні залежності:
- `sqlalchemy>=2.0.0`
- `pydantic>=2.0.0`
- `pydantic-settings>=2.0.0`
- `python-dotenv>=1.0.0`

### 2. `.gitignore`
Включити:
- `__pycache__/`, `*.pyc`
- `venv/`, `.env`
- `data/*.db` (база даних не комітиться)

### 3. `src/config.py`
- Конфігурація шляхів через Pydantic `BaseSettings`:
  - `DB_PATH`: шлях до файлу БД (за замовчуванням `data/app.db`).
  - Створення папки `data/`, якщо вона відсутня.

### 4. `src/database/connection.py`
- Ініціалізація `engine` для SQLite (`sqlite:///...`).
- Фабрика сесій `sessionmaker(autocommit=False, autoflush=False, bind=engine)`.
- Базовий декларативний клас `Base = declarative_base()`.
- Допоміжна функція `get_db()` (генератор сесії для подальшого використання у сервісах/FastAPI).

### 5. `src/database/models.py`
Описати 4 ключові таблиці зі зв'язками (ForeignKeys) та індексами:

1. **`products` (Наші власні товари):**
   - `id`: Integer, Primary Key, autoincrement.
   - `sku`: String, unique=True, index=True (артикул товару).
   - `title`: String, nullable=False.
   - `category`: String, nullable=True.
   - `current_price`: Float, nullable=False.
   - `cost_price`: Float, nullable=False (собівартість).
   - `min_margin_percent`: Float, default=15.0 (мінімальна маржа у %).
   - `image_url`: String, nullable=True.
   - `is_active`: Boolean, default=True.
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow.
   - `updated_at`: DateTime(timezone=True), onupdate=datetime.utcnow.

2. **`competitor_offers` (Пропозиції конкурентів із Prom.ua):**
   - `id`: Integer, Primary Key, autoincrement.
   - `source`: String, default="prom.ua" (джерело).
   - `external_id`: String, nullable=True, index=True (ID товару на маркетплейсі).
   - `title`: String, nullable=False (назва товару у конкурента).
   - `price`: Float, nullable=False.
   - `seller_name`: String, nullable=True (назва магазину на Prom).
   - `url`: String, nullable=False (пряме посилання).
   - `image_url`: String, nullable=True.
   - `is_in_stock`: Boolean, default=True (наявність).
   - `scraped_at`: DateTime(timezone=True), default=datetime.utcnow.

3. **`product_matches` (Зв'язок нашого товару та товару конкурента):**
   - `id`: Integer, Primary Key, autoincrement.
   - `product_id`: Integer, ForeignKey("products.id"), index=True.
   - `competitor_offer_id`: Integer, ForeignKey("competitor_offers.id"), index=True.
   - `match_method`: String (наприклад: "exact_sku", "fuzzy_title", "ai_gemini").
   - `confidence_score`: Float, nullable=False (від 0.0 до 1.0).
   - `status`: String, default="pending" ("pending", "approved", "rejected").
   - `ai_reasoning`: Text, nullable=True (коротке обґрунтування від моделі).
   - `matched_at`: DateTime(timezone=True), default=datetime.utcnow.

4. **`price_recommendations` (Рекомендовані ціни та історія):**
   - `id`: Integer, Primary Key, autoincrement.
   - `product_id`: Integer, ForeignKey("products.id"), index=True.
   - `current_price`: Float, nullable=False.
   - `min_market_price`: Float, nullable=False (найнижча валідна ціна серед схвалених конкурентів).
   - `recommended_price`: Float, nullable=False.
   - `status`: String, default="pending" ("pending", "applied", "dismissed").
   - `calculated_at`: DateTime(timezone=True), default=datetime.utcnow.

### 6. `scripts/init_db.py`
Скрипт перевірки:
- Створює таблиці в БД (`Base.metadata.create_all(bind=engine)`).
- Додає 1 тестовий товар у `products` (наприклад, чохол чи павербанк).
- Робить вибірку доданого товару з БД та виводить у консоль підтвердження успішного запису.

---

## Критерії приймання та перевірка (Verification)
1. Створено віртуальне середовище, встановлено залежності з `requirements.txt`.
2. Виконання команди:
   ```bash
   python scripts/init_db.py
   ```
3. Скрипт успішно завершується з кодом 0, у папці `data/` з'являється файл `app.db`, а в консолі виводиться тестовий запис.

---

## Формат звіту після виконання
1. Список створених файлів.
2. Результат виконання тестового скрипту `init_db.py`.
3. Єдина команда для збереження змін:
   `git add . && git commit -m "feat: initialize project structure and database schema" && git push origin main`
