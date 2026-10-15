# ТЗ №5: Двигун динамічного ціноутворення (Repricing Engine & Recommendations)

## Мета
Реалізувати сервіс динамічного ціноутворення (`PricingEngine`), який аналізує ринкові ціни лише за схваленими пропозиціями конкурентів у наявності (`status == 'approved'`, `is_in_stock == True`), розраховує безпечну рекомендовану ціну із захистом мінімальної маржі магазину (`Floor Price`), зберігає історію в таблицю `price_recommendations` та надає можливість застосування нових цін до каталогу `products`.

---

## Стек технологій
- **Мова:** Python 3.11+
- **База даних:** SQLAlchemy 2.0+ (`Product`, `CompetitorOffer`, `ProductMatch`, `PriceRecommendation`)
- **CLI:** `argparse`

---

## Структура файлів до створення / модифікації
```text
/home/dofi/Dev/aiparsing/
├── src/
│   └── services/
│       └── pricing_engine.py          # Сервіс розрахунку рекомендованих цін та захисту маржі
└── scripts/
    └── calculate_prices.py            # CLI скрипт для запуску репрайсингу та застосування цін
```

---

## Детальні вимоги до реалізації

### 1. Сервіс ціноутворення `src/services/pricing_engine.py`
Створити клас `PricingEngine`:

- **Логіка розрахунку для одного товару (`calculate_for_product(db: Session, product: Product, delta: float = 5.0) -> PriceRecommendation`):**
  1. **Вибірка валідних конкурентів:**
     - Знайти всі `ProductMatch`, де `product_id == product.id` та `status == 'approved'`.
     - Відфільтрувати пов'язані `CompetitorOffer`, де `is_in_stock == True` та `price > 0`.
  2. **Розрахунок захисного порогу (Floor Price):**
     - $$\text{floor\_price} = \text{product.cost\_price} \times \left(1.0 + \frac{\text{product.min\_margin\_percent}}{100.0}\right)$$
     - Роздрібна ціна за жодних умов не може бути нижчою за це значення.
  3. **Сценарії визначення ціни:**
     - **Якщо валідних конкурентів немає в наявності:**
       - $\text{min\_market\_price} = \text{product.current\_price}$
       - $\text{recommended\_price} = \text{product.current\_price}$
       - Примітка: *"Немає активних пропозицій конкурентів у наявності. Ціну збережено без змін."*
     - **Якщо конкуренти є:**
       - $\text{min\_market\_price} = \min(\text{competitor\_prices})$
       - Цільова ціна для виходу в топ видачі:
         $$\text{target\_price} = \text{min\_market\_price} - \text{delta}$$
       - Фінальна рекомендована ціна з урахуванням захисту собівартості:
         $$\text{recommended\_price} = \max(\text{target\_price}, \text{floor\_price})$$
       - Округлення до 2 знаків після коми: `round(recommended_price, 2)`.
  4. **Збереження результату:**
     - Створює запис у таблиці `PriceRecommendation`:
       - `product_id = product.id`
       - `current_price = product.current_price`
       - `min_market_price = min_market_price`
       - `recommended_price = recommended_price`
       - `status = "pending"`
       - `calculated_at = datetime.now(timezone.utc)`
     - Додає запис у сесію БД та зберігає.
     - Повертає об'єкт `PriceRecommendation`.

- **Метод `calculate_all(db: Session, delta: float = 5.0) -> list[PriceRecommendation]`:**
  - Проходить по всіх активних товарах каталогу (`Product.is_active == True`).
  - Розраховує та зберігає рекомендації для кожного товару.

- **Метод `apply_recommendations(db: Session, recommendation_ids: Optional[list[int]] = None) -> int`:**
  - Оновлює поточну ціну товару `product.current_price = rec.recommended_price`.
  - Змінює статус рекомендації на `rec.status = "applied"`.
  - Оновлює `product.updated_at = datetime.now(timezone.utc)`.
  - Повертає кількість успішно застосованих цін.

---

### 2. CLI скрипт `scripts/calculate_prices.py`
Аргументи командного рядка:
- `--delta`: крок зниження відносно мінімальної ціни конкурента (float, за замовчуванням `5.0`).
- `--apply`: прапорець (boolean), якщо вказано — відразу застосувати рекомендовані ціни до каталогу товарів у БД.
- Інформативний вивід у консоль:
  ```text
  Запуск розрахунку цін (Repricing Engine)...
  Крок дельти: 5.0 грн | Режим застосування: [Тільки розрахунок / Застосувати в базу]
  --------------------------------------------------------------------------------------------------------
  [SKU: PPDGL-01] Павербанк Baseus Blade 100W 20000mAh Black
    Собівартість: 1850.0 грн | Поточна: 2699.0 грн | Поріг маржі (Floor): 2127.5 грн
    Мінімальний конкурент: 3324.0 грн (схвалено оферів: 4)
    -> Рекомендована ціна: 3319.0 грн [▲ +620.0 грн до прибутку магазину]
  
  [SKU: C80A-WHT] ...
  --------------------------------------------------------------------------------------------------------
  Підсумок аналізу цін:
  - Товарів переоцінено вгору (Underpriced): 1
  - Товарів переоцінено вниз (Overpriced): 0
  - Без змін / Немає конкурентів: 11
  - Захист собівартості: 0 порушень
  Рекомендації успішно збережено в базі даних!
  ```

---

## Критерії приймання та верифікація (Verification)
1. Розрахунок цін без перезапису каталогу:
   ```bash
   venv/bin/python scripts/calculate_prices.py --delta 5.0
   ```
   *Очікуваний результат:* у таблиці `price_recommendations` з'являються записи зі статусом `pending`. Для товару `PPDGL-01` рекомендована ціна має бути в районі ~3319 грн (підняття під ринок із захистом маржі).
2. Перевірка таблиці рекомендацій:
   ```bash
   venv/bin/python -c "from src.database.connection import SessionLocal; from src.database.models import PriceRecommendation; db = SessionLocal(); recs = db.query(PriceRecommendation).all(); print(f'Total recommendations: {len(recs)}'); [print(f'Product {r.product_id}: was {r.current_price} -> rec {r.recommended_price} (min market: {r.min_market_price})') for r in recs]; assert len(recs) > 0; db.close()"
   ```
3. Застосування рекомендацій:
   ```bash
   venv/bin/python scripts/calculate_prices.py --delta 5.0 --apply
   ```
   *Очікуваний результат:* статус рекомендацій стає `applied`, а в таблиці `products` оновлюється `current_price`.

---

## Формат звіту після виконання
1. Список створених/модифікованих файлів.
2. Лог виконання команди `calculate_prices.py` (розрахунок та застосування).
3. Перевірка оновлених цін у базі даних.
4. Єдина команда для git фіксації:
   `git add . && git commit -m "feat: implement dynamic repricing engine with margin protection" && git push origin main`
