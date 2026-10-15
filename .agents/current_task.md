# ТЗ №4: Інтелектуальний модуль зіставлення товарів (AI & Fuzzy Matching Engine)

## Мета
Реалізувати дворівневий модуль зіставлення (Level 1: швидкий fuzzy/rule-based фільтр + Level 2: AI-арбітр на базі Google Gemini 2.5 Flash), який порівнює наші товари з зібраними пропозиціями конкурентів, оцінює відсоток впевненості (`confidence_score` 0.0 - 1.0) та заповнює таблицю `product_matches`.

---

## Стек технологій та залежності
- **Fuzzy Matching:** `rapidfuzz>=3.0.0`
- **AI SDK:** `google-genai>=0.1.0`
- **Модель AI:** `gemini-2.5-flash` (ключ береться з `.env`)
- **База даних:** SQLAlchemy (`Product`, `CompetitorOffer`, `ProductMatch`)

---

## Структура файлів до створення / модифікації
```text
/home/dofi/Dev/aiparsing/
├── requirements.txt                   # Додати rapidfuzz>=3.0.0 та google-genai>=0.1.0
├── src/
│   ├── config.py                      # Додати параметри GEMINI_API_KEY, GEMINI_MODEL
│   └── services/
│       ├── discovery_service.py       # Додати створення ProductMatch зв'язки при збереженні оферів
│       ├── ai_matcher.py              # Клієнт Google Gemini для порівняння товарів у JSON форматі
│       └── matching_engine.py         # Дворівневий оркестратор зіставлення (Rules + Fuzzy + AI)
└── scripts/
    └── match_products.py              # CLI скрипт для запуску процесу матчингу
```

---

## Детальні вимоги до реалізації

### 1. Оновлення `requirements.txt`
Додати:
- `rapidfuzz>=3.0.0`
- `google-genai>=0.1.0`

### 2. Оновлення `src/config.py`
Додати зчитування параметрів для Gemini:
- `gemini_api_key: Optional[str] = None` (зчитується з `GEMINI_API_KEY` або `.env`)
- `gemini_model: str = "gemini-2.5-flash"` (зчитується з `GEMINI_MODEL` або дефолт)

### 3. Оновлення `src/services/discovery_service.py`
- При знаходженні пропозиції для `product`:
  - Крім збереження/оновлення `CompetitorOffer`, перевіряти наявність запису `ProductMatch(product_id=product.id, competitor_offer_id=offer.id)`.
  - Якщо зв'язки немає — створювати запис `ProductMatch` зі статусом `pending`, `confidence_score=0.0`, `match_method="discovered"`.
  - Якщо вже існує — залишати без змін.
- Забезпечити збереження в БД.

### 4. Модуль AI-зіставлення `src/services/ai_matcher.py`
Створити клас `GeminiMatcher`:
- Ініціалізується з `api_key` та `model_name`.
- **Метод `compare(our_title: str, our_sku: str, our_price: float, comp_title: str, comp_price: float) -> dict`:**
  - Якщо `api_key` відсутній — повертає `{"is_same_product": False, "confidence": 0.5, "reasoning": "Gemini API key not configured"}`.
  - Формує запит до моделі порівняти товар нашого магазину і товар конкурента.
  - Використовує структурований JSON-вихід (`response_mime_type="application/json"`).
  - Очікувана схема відповіді:
    ```json
    {
      "is_same_product": true,
      "confidence": 0.95,
      "reasoning": "Пояснення українською мовою щодо відповідності моделі, ємності, кольору тощо."
    }
    ```
  - Обробляє можливі помилки запиту та таймаути (fallback на safe default).

### 5. Сервіс матчингу `src/services/matching_engine.py`
Створити клас `MatchingEngine`:
- **Логіка оцінки відповідності (`evaluate_match(product: Product, offer: CompetitorOffer, force_ai: bool = False) -> MatchResult`):**
  1. **Крок A (Exact SKU / Артикул):**
     - Якщо `product.sku` (довжиною >= 3 символи) присутній у `offer.title` (case-insensitive):
       $\rightarrow$ `confidence = 0.98`, `method = "exact_sku"`, `reasoning = f"Точний збіг артикулу {product.sku}"`.
  2. **Крок B (Rule-based невідповідності):**
     - Перевірка несумісності ключових чисел: якщо у нашого товару є потужність (наприклад `100W`), а у конкурента явно інша (наприклад `65W`) $\rightarrow$ `confidence = 0.15`, `method = "rule_based"`, `reasoning = "Невідповідність ключових характеристик (потужність/модель)"`.
     - Якщо різні бренди (наприклад наш Baseus, а у конкурента Xiaomi або Hoco) $\rightarrow$ `confidence = 0.10`, `method = "rule_based"`, `reasoning = "Різні бренди"`.
  3. **Крок C (Текстовий Fuzzy-аналіз через `rapidfuzz`):**
     - Розрахунок `similarity = rapidfuzz.fuzz.token_set_ratio(product.title, offer.title) / 100.0`.
     - Якщо `similarity >= 0.90` $\rightarrow$ `confidence = similarity`, `method = "fuzzy_title"`.
  4. **Крок D (AI Арбітр через `GeminiMatcher`):**
     - Якщо оцінка знаходиться в «сірій зоні» (`0.45 <= similarity < 0.90`) або якщо передано `force_ai=True`:
       - Викликається `GeminiMatcher.compare(...)`.
       - Береться `confidence` та `reasoning` від моделі, `method = "ai_gemini"`.
  5. **Крок E (Фінальний статус):**
     - `status = "approved"` якщо `confidence >= 0.80` та `offer.is_in_stock == True`.
     - `status = "rejected"` якщо `confidence < 0.50` або `is_same_product == False`.
     - `status = "pending"` у проміжних випадках.
- **Метод `process_pending_matches(db: Session, force_ai: bool = False) -> list[ProductMatch]`:**
  - Знаходить усі `ProductMatch` зі статусом `pending` (або створює їх для існуючих зв'язок, якщо ще не створені).
  - Запускає `evaluate_match`, оновлює поля `confidence_score`, `match_method`, `status`, `ai_reasoning`.
  - Зберігає зміни в БД.

### 6. CLI скрипт `scripts/match_products.py`
- Аргументи:
  - `--force-ai`: примусово опитувати Gemini для всіх кандидатів (за замовчуванням тільки для спірних або без точного SKU).
  - `--link-existing`: перед матчингом автоматично створити записи `ProductMatch` для вже зібраних `CompetitorOffer`, якщо вони ще не прив'язані.
- Вивід у консоль гарної підсумкової таблиці:
  ```text
  Запуск оцінки відповідності товарів (Matching Engine)...
  --------------------------------------------------------------------------------------------------------
  Наш товар: Павербанк Baseus Blade 100W 20000mAh Black (PPDGL-01)
    [98%] APPROVED (exact_sku): УМБ Baseus PPDGL-01 20000mAh, 100W (4043.0 грн)
          -> Точний збіг артикулу PPDGL-01
    [15%] REJECTED (rule_based): Повербанк Baseus Blade H1 65W 20000mAh (3299.0 грн)
          -> Невідповідність характеристик (65W vs 100W)
    [95%] APPROVED (ai_gemini): Павербанк Baseus Blade Digital Display 20000 mAh PD 100W Black (3324.0 грн)
          -> Обидва товари ідентичні: модель Baseus Blade 100W 20000mAh
  --------------------------------------------------------------------------------------------------------
  Всього оброблено зв'язок: 11
  Схвалено (Approved): 4 | Відхилено (Rejected): 6 | На ручній перевірці (Pending): 1
  ```

---

## Критерії приймання та верифікація (Verification)
1. Встановлено залежності:
   ```bash
   venv/bin/pip install -r requirements.txt
   ```
2. Запуск матчингу:
   ```bash
   venv/bin/python scripts/match_products.py --link-existing
   ```
3. Перевірка бази даних:
   ```bash
   venv/bin/python -c "from src.database.connection import SessionLocal; from src.database.models import ProductMatch; db = SessionLocal(); matches = db.query(ProductMatch).all(); print(f'Total matches in DB: {len(matches)}'); [print(f'[{m.status.upper()}] {m.confidence_score*100:.0f}% ({m.match_method}): {m.ai_reasoning[:60]}...') for m in matches[:5]]; assert len(matches) > 0; db.close()"
   ```
   *Очікуваний результат:* у таблиці `product_matches` з'явилися записи зі статусами `approved` та `rejected`, заповненими `confidence_score` та детальним обґрунтуванням `ai_reasoning`.

---

## Формат звіту після виконання
1. Список створених/модифікованих файлів.
2. Лог виконання команди `scripts/match_products.py --link-existing`.
3. Результат перевірки бази даних.
4. Єдина команда для git фіксації:
   `git add . && git commit -m "feat: implement hybrid AI and fuzzy matching engine with Gemini" && git push origin main`
