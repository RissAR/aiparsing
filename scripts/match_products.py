import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database.connection import SessionLocal
from src.database.models import CompetitorOffer, Product
from src.services.matching_engine import MatchingEngine, MatchResult


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Інтелектуальне зіставлення товарів із пропозиціями конкурентів (Rules + Fuzzy + AI)"
    )
    parser.add_argument(
        "--force-ai",
        action="store_true",
        help="Примусово опитувати Gemini для всіх кандидатів",
    )
    parser.add_argument(
        "--link-existing",
        action="store_true",
        help="Автоматично створити ProductMatch для вже зібраних оферів перед матчингом",
    )
    args = parser.parse_args()

    print("Запуск оцінки відповідності товарів (Matching Engine)...")
    print("-" * 104)

    engine = MatchingEngine()
    current_product_id: Optional[int] = None
    evaluated_statuses: list[str] = []

    def on_match(product: Product, offer: CompetitorOffer, res: MatchResult) -> None:
        nonlocal current_product_id
        if product.id != current_product_id:
            sku_suffix = f" ({product.sku})" if product.sku else ""
            print(f"Наш товар: {product.title}{sku_suffix}")
            current_product_id = product.id

        pct = int(res.confidence_score * 100)
        status_str = res.status.upper()
        print(f"  [{pct}%] {status_str} ({res.match_method}): {offer.title} ({offer.price:.1f} грн)")
        print(f"        -> {res.ai_reasoning}")
        evaluated_statuses.append(res.status)

    with SessionLocal() as db:
        if args.link_existing:
            linked = engine.link_existing_offers(db)
            if linked > 0:
                print(f"Прив'язано існуючих оферів до товарів: {linked}")

        engine.process_pending_matches(
            db=db,
            force_ai=args.force_ai,
            on_match_evaluated=on_match,
        )

    approved = sum(1 for s in evaluated_statuses if s == "approved")
    rejected = sum(1 for s in evaluated_statuses if s == "rejected")
    pending = sum(1 for s in evaluated_statuses if s == "pending")
    total = len(evaluated_statuses)

    print("-" * 104)
    print(f"Всього оброблено зв'язок: {total}")
    print(f"Схвалено (Approved): {approved} | Відхилено (Rejected): {rejected} | На ручній перевірці (Pending): {pending}")


if __name__ == "__main__":
    main()
