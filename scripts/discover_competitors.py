import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database.connection import SessionLocal
from src.services.discovery_service import DiscoveryService, ProductDiscoveryResult


def print_progress(idx: int, total: int, res: ProductDiscoveryResult) -> None:
    print(f"[{idx}/{total}] Наш товар: {res.product.title} (SKU: {res.product.sku})")
    print(f"      Пошуковий запит: '{res.query}'")
    print(f"      -> Знайдено оферів: {res.found_count}")
    if res.min_price is not None and res.max_price is not None:
        if res.min_price == res.max_price:
            print(f"      -> Збережено в базу (ціна: {res.min_price} UAH)")
        else:
            print(f"      -> Збережено в базу (діапазон цін: {res.min_price} - {res.max_price} UAH)")
    else:
        print("      -> Збережено в базу (пропозицій не знайдено)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Пошук та збір конкурентів на Prom.ua для активних товарів з бази"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Кількість товарів з каталогу для обробки (за замовчуванням: 3)",
    )
    parser.add_argument(
        "--offers-per-product",
        type=int,
        default=5,
        help="Скільки конкурентів збирати для кожного товару (за замовчуванням: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Пауза між товарами в секундах (за замовчуванням: 1.5)",
    )
    args = parser.parse_args()

    print("Запуск пошуку конкурентів на Prom.ua...")
    print(
        f"Товарів до обробки: {args.limit} | "
        f"Оферів на товар: {args.offers_per_product} | "
        f"Затримка: {args.delay}s"
    )
    print("------------------------------------------------------------")

    service = DiscoveryService()

    with SessionLocal() as db:
        results = service.discover_all(
            db=db,
            limit_products=args.limit,
            offers_per_product=args.offers_per_product,
            delay_seconds=args.delay,
            on_progress=print_progress,
        )

    total_saved = sum(r.saved_count for r in results)
    print("------------------------------------------------------------")
    print(f"Пошук завершено. Всього зібрано пропозицій: {total_saved}")


if __name__ == "__main__":
    main()
