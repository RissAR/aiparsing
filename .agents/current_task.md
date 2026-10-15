# ТЗ №2: Модуль імпорту власного каталогу (XML/YML Ingestion)

## Мета
Реалізувати надійний сервіс парсингу та імпорту товарних фідів Prom.ua (формат XML/YML) у базу даних `products` з підтримкою операцій додавання нових та оновлення існуючих позицій (Upsert), а також підготувати реалістичний тестовий набір даних (електроніка та мобільні аксесуари).

---

## Стек технологій та залежності
- **Парсинг XML:** `lxml>=5.0.0` (додати до `requirements.txt`)
- **База даних:** SQLAlchemy 2.0+ (моделі з Кроку 1)
- **CLI аргументи:** стандартна бібліотека `argparse`

---

## Структура файлів до створення / модифікації
```text
/home/dofi/Dev/aiparsing/
├── requirements.txt                   # Додати lxml>=5.0.0
├── data/
│   └── samples/
│       └── prom_feed.xml              # Тестовий XML/YML фід Prom.ua на 10-12 товарів
├── src/
│   └── services/
│       ├── __init__.py
│       └── feed_importer.py           # Сервіс парсингу та upsert-логіки
└── scripts/
    └── import_feed.py                 # CLI скрипт запуску імпорту
```

---

## Детальні вимоги до реалізації

### 1. Оновлення `requirements.txt`
Додати:
- `lxml>=5.0.0`

### 2. Тестовий фід `data/samples/prom_feed.xml`
Створити валідний XML-фід за стандартом YML / Prom.ua, що містить секцію `<yml_catalog>` $\rightarrow$ `<shop>` $\rightarrow$ `<offers>` із 10–12 популярними товарами електроніки та мобільних аксесуарів (Baseus, Hoco, Xiaomi, Apple accessories).
Кожен `<offer>` повинен містити:
- `id` (унікальний числовий ідентифікатор офера в Prom)
- `available="true"`
- `<name>`: Реалістична комерційна назва (наприклад, *"Павербанк Baseus Blade 100W 20000mAh Black (PPDGL-01)"*, *"Мережевий зарядний пристрій Hoco C80A Dual Port 20W White"*, *"Кабель Type-C to Lightning Baseus Cafule 20W 1m"*)
- `<vendorCode>`: Реальний артикул виробника (SKU)
- `<price>`: Роздрібна ціна (число)
- `<currencyId>UAH</currencyId>`
- `<categoryId>`: ID категорії
- `<picture>`: Посилання на фото
- `<vendor>`: Бренд (Baseus, Hoco тощо)
- Опціонально для частини товарів: `<param name="Собівартість">1800</param>` або `<cost_price>1800</cost_price>` для тестування парсингу закупівлі.

### 3. Сервіс імпорту `src/services/feed_importer.py`
Створити клас `FeedImporter`:
- **Метод `import_from_file(file_path: str) -> ImportResult`:**
  - Парсить XML за допомогою `lxml.etree`.
  - Валідує наявність обов'язкових полів: `name`, `price`, `vendorCode` (якщо `vendorCode` відсутній — брати `offer.get('id')` як fallback).
  - **Логіка собівартості (`cost_price`):**
    1. Перевіряє наявність тегу `<cost_price>` або `<param name="Собівартість">` / `<param name="Закупка">`.
    2. Якщо собівартості у фіді немає — вираховує автоматично як `price * 0.75` (дефолтна маржа 25%).
  - **Upsert логіка (по полю `sku`):**
    - Якщо товар із таким `sku` вже існує в БД:
      - Оновлює: `current_price`, `title`, `image_url`, `is_active` (`available == 'true'`), `updated_at`.
      - Собівартість оновлює тільки якщо вона явно передана у фіді.
      - Збільшує лічильник `updated`.
    - Якщо товару немає:
      - Створює новий запис `Product` у БД.
      - Збільшує лічильник `created`.
  - Повертає dataclass або Pydantic-об'єкт `ImportResult`:
    - `total_offers: int`
    - `created: int`
    - `updated: int`
    - `errors: list[str]`

### 4. CLI скрипт `scripts/import_feed.py`
Скрипт із підтримкою аргументів:
- Аргумент командного рядка:
  `--file`: обов'язковий або дефолтний шлях до файлу (за замовчуванням `data/samples/prom_feed.xml`).
- Виводить у консоль інформативний прогрес та підсумок:
  ```text
  Імпорт фіду: data/samples/prom_feed.xml
  ----------------------------------------
  Всього оферів у фіді: 12
  Успішно створено нових: 12
  Оновлено існуючих: 0
  Помилок: 0
  ----------------------------------------
  Імпорт успішно завершено!
  ```

---

## Критерії приймання та верифікація (Verification)
1. Встановлено нові залежності:
   ```bash
   pip install -r requirements.txt
   ```
2. Перший запуск імпорту:
   ```bash
   python scripts/import_feed.py --file data/samples/prom_feed.xml
   ```
   *Очікуваний результат:* створено 10-12 нових товарів, 0 помилок.
3. Повторний запуск імпорту (перевірка ідемпотентності / Upsert):
   ```bash
   python scripts/import_feed.py --file data/samples/prom_feed.xml
   ```
   *Очікуваний результат:* створено 0, оновлено 10-12, дублікатів у базі не з'явилося.

---

## Формат звіту після виконання
1. Список створених/модифікованих файлів.
2. Лог виконання команд верифікації (перший та другий запуск).
3. Єдина команда для git фіксації:
   `git add . && git commit -m "feat: implement XML/YML catalog ingestion service and CLI" && git push origin main`
