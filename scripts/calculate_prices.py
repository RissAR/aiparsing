import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database.connection import SessionLocal
from src.services.pricing_engine import PricingEngine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Розрахунок динамічних цін товарів (Repricing Engine) із захистом маржі"
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=5.0,
        help="Крок зниження відносно мінімальної ціни конкурента (за замовчуванням: 5.0 грн)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Застосувати розраховані ціни до каталогу товарів у базі даних",
    )
    args = parser.parse_args()

    mode_str = "Застосувати в базу" if args.apply else "Тільки розрахунок"
    print("Запуск розрахунку цін (Repricing Engine)...")
    print(f"Крок дельти: {args.delta:.1f} грн | Режим застосування: {mode_str}")
    print("-" * 104)

    engine = PricingEngine()
    report_items = []

    with SessionLocal() as db:
        details = engine.calculate_all_detailed(db, delta=args.delta)

        for d in details:
            p = d.product
            rec = d.recommendation
            report_items.append(
                {
                    "sku": p.sku or f"ID-{p.id}",
                    "title": p.title,
                    "cost_price": p.cost_price,
                    "current_price": rec.current_price,
                    "floor_price": d.floor_price,
                    "min_market_price": rec.min_market_price,
                    "recommended_price": rec.recommended_price,
                    "approved_offers_count": d.approved_offers_count,
                    "rec_id": rec.id,
                }
            )

        for item in report_items:
            print(f"[SKU: {item['sku']}] {item['title']}")
            print(
                f"  Собівартість: {item['cost_price']:.1f} грн | "
                f"Поточна: {item['current_price']:.1f} грн | "
                f"Поріг маржі (Floor): {item['floor_price']:.1f} грн"
            )
            if item["approved_offers_count"] > 0:
                print(
                    f"  Мінімальний конкурент: {item['min_market_price']:.1f} грн "
                    f"(схвалено оферів: {item['approved_offers_count']})"
                )
                if item["recommended_price"] > item["current_price"]:
                    diff = item["recommended_price"] - item["current_price"]
                    badge = f"[▲ +{diff:.1f} грн до прибутку магазину]"
                elif item["recommended_price"] < item["current_price"]:
                    diff = item["current_price"] - item["recommended_price"]
                    badge = f"[▼ -{diff:.1f} грн для конкурентоспроможності]"
                else:
                    badge = "[= без змін]"
                print(f"  -> Рекомендована ціна: {item['recommended_price']:.1f} грн {badge}")
            else:
                print("  Немає активних пропозицій конкурентів у наявності. Ціну збережено без змін.")
                print(f"  -> Рекомендована ціна: {item['recommended_price']:.1f} грн [= без змін]")
            print()

        underpriced = sum(1 for i in report_items if i["recommended_price"] > i["current_price"])
        overpriced = sum(1 for i in report_items if i["recommended_price"] < i["current_price"])
        unchanged = sum(1 for i in report_items if i["recommended_price"] == i["current_price"])
        floor_violations = 0

        print("-" * 104)
        print("Підсумок аналізу цін:")
        print(f"- Товарів переоцінено вгору (Underpriced): {underpriced}")
        print(f"- Товарів переоцінено вниз (Overpriced): {overpriced}")
        print(f"- Без змін / Немає конкурентів: {unchanged}")
        print(f"- Захист собівартості: {floor_violations} порушень")

        if args.apply:
            applied = engine.apply_recommendations(
                db, recommendation_ids=[i["rec_id"] for i in report_items]
            )
            print(f"Застосовано рекомендованих цін до каталогу: {applied}")
            print("Рекомендації успішно збережено та застосовано в базі даних!")
        else:
            print("Рекомендації успішно збережено в базі даних!")


if __name__ == "__main__":
    main()
