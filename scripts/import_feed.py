import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.services.feed_importer import FeedImporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Імпорт товарного фіду Prom.ua (XML/YML)")
    parser.add_argument(
        "--file",
        type=str,
        default="data/samples/prom_feed.xml",
        help="Шлях до XML файлу каталогу (за замовчуванням: data/samples/prom_feed.xml)",
    )
    args = parser.parse_args()

    feed_path = Path(args.file)
    if not feed_path.is_absolute():
        feed_path = BASE_DIR / feed_path

    print(f"Імпорт фіду: {args.file}")
    print("----------------------------------------")

    importer = FeedImporter()
    result = importer.import_from_file(feed_path)

    print(f"Всього оферів у фіді: {result.total_offers}")
    print(f"Успішно створено нових: {result.created}")
    print(f"Оновлено існуючих: {result.updated}")
    print(f"Помилок: {len(result.errors)}")
    print("----------------------------------------")

    if result.errors:
        print("Деталі помилок:")
        for err in result.errors:
            print(f"  - {err}")
        print("----------------------------------------")

    print("Імпорт успішно завершено!")


if __name__ == "__main__":
    main()
