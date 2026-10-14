import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.database.connection import Base, SessionLocal, engine
from src.database.models import Product


def init_db() -> None:
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    with SessionLocal() as session:
        test_sku = "PB-BASEUS-100W"
        product = session.query(Product).filter_by(sku=test_sku).first()

        if not product:
            product = Product(
                sku=test_sku,
                title="Павербанк Baseus Blade 100W 20000mAh Black",
                category="Power Banks",
                current_price=2499.00,
                cost_price=1750.00,
                min_margin_percent=15.0,
                image_url="https://example.com/images/pb-baseus-100w.jpg",
                is_active=True,
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            print(f"Created test product: ID={product.id}, SKU={product.sku}")
        else:
            print(f"Test product already exists: ID={product.id}, SKU={product.sku}")

        # Verification query
        queried = session.query(Product).filter_by(sku=test_sku).first()
        if queried:
            print(f"Verification successful: retrieved product '{queried.title}' (SKU: {queried.sku})")
            print(f"Price: {queried.current_price} UAH | Cost: {queried.cost_price} UAH | Margin: {queried.min_margin_percent}%")
            print(f"Database path: {engine.url}")
        else:
            raise RuntimeError("Failed to verify product insertion in database!")


if __name__ == "__main__":
    init_db()
