from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from lxml import etree
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.connection import SessionLocal
from src.database.models import Product


class ImportResult(BaseModel):
    """Result of catalog feed ingestion."""

    total_offers: int = 0
    created: int = 0
    updated: int = 0
    errors: list[str] = Field(default_factory=list)


class FeedImporter:
    """Service for parsing and upserting Prom.ua XML/YML product feeds."""

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session = session

    def import_from_file(self, file_path: str | Path) -> ImportResult:
        """Parse XML feed from disk and upsert products into database."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Feed file not found: {file_path}")

        if self.session is not None:
            return self._process_feed(self.session, path)

        with SessionLocal() as session:
            try:
                result = self._process_feed(session, path)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise

    def _process_feed(self, session: Session, file_path: Path) -> ImportResult:
        result = ImportResult()

        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        try:
            tree = etree.parse(str(file_path), parser=parser)
        except Exception as e:
            result.errors.append(f"Failed to parse XML: {e}")
            return result

        root = tree.getroot()
        if root is None:
            result.errors.append("XML document has no root element")
            return result

        # Extract category mapping (ID -> Name)
        categories_map: dict[str, str] = {}
        for cat in root.xpath(".//categories/category"):
            cat_id = cat.get("id")
            cat_name = cat.text
            if cat_id and cat_name:
                categories_map[cat_id.strip()] = cat_name.strip()

        offers = root.xpath(".//offers/offer")
        result.total_offers = len(offers)

        for offer in offers:
            offer_id = offer.get("id")

            # 1. Title validation
            name_elem = offer.find("name")
            if name_elem is None or not name_elem.text or not name_elem.text.strip():
                result.errors.append(f"Offer ID '{offer_id}': Missing required <name>")
                continue
            title = name_elem.text.strip()

            # 2. Price validation
            price_elem = offer.find("price")
            if price_elem is None or not price_elem.text or not price_elem.text.strip():
                result.errors.append(f"Offer ID '{offer_id}': Missing required <price>")
                continue
            try:
                price = float(price_elem.text.strip().replace(",", "."))
            except ValueError:
                result.errors.append(
                    f"Offer ID '{offer_id}': Invalid price format '{price_elem.text.strip()}'"
                )
                continue

            # 3. SKU validation with fallback to offer id
            vendor_code_elem = offer.find("vendorCode")
            if (
                vendor_code_elem is not None
                and vendor_code_elem.text
                and vendor_code_elem.text.strip()
            ):
                sku = vendor_code_elem.text.strip()
            elif offer_id and offer_id.strip():
                sku = str(offer_id).strip()
            else:
                result.errors.append(
                    f"Offer '{title}': Missing both <vendorCode> and 'id' attribute"
                )
                continue

            # 4. Optional fields: category and image_url
            category_elem = offer.find("categoryId")
            category: Optional[str] = None
            if category_elem is not None and category_elem.text and category_elem.text.strip():
                cat_id = category_elem.text.strip()
                category = categories_map.get(cat_id, cat_id)

            picture_elem = offer.find("picture")
            image_url: Optional[str] = None
            if picture_elem is not None and picture_elem.text and picture_elem.text.strip():
                image_url = picture_elem.text.strip()

            # Availability
            available_val = (offer.get("available") or "true").strip().lower()
            is_active = available_val in ("true", "1", "yes")

            # 5. Cost price logic
            cost_price, is_explicit_cost = self._extract_cost_price(offer, price)

            # 6. Upsert logic by SKU
            existing_product = session.query(Product).filter_by(sku=sku).first()
            if existing_product:
                existing_product.title = title
                existing_product.current_price = price
                existing_product.is_active = is_active
                if image_url is not None:
                    existing_product.image_url = image_url
                if category is not None:
                    existing_product.category = category
                if is_explicit_cost:
                    existing_product.cost_price = cost_price
                existing_product.updated_at = datetime.now(timezone.utc)
                result.updated += 1
            else:
                new_product = Product(
                    sku=sku,
                    title=title,
                    category=category,
                    current_price=price,
                    cost_price=cost_price,
                    image_url=image_url,
                    is_active=is_active,
                    min_margin_percent=15.0,
                )
                session.add(new_product)
                result.created += 1

        return result

    @staticmethod
    def _extract_cost_price(offer: etree._Element, price: float) -> tuple[float, bool]:
        """Extract explicit cost price or compute fallback with 25% margin."""
        # 1. Check <cost_price> tag
        cp_elem = offer.find("cost_price")
        if cp_elem is not None and cp_elem.text and cp_elem.text.strip():
            try:
                return float(cp_elem.text.strip().replace(",", ".")), True
            except ValueError:
                pass

        # 2. Check <param name="..."> tags
        for param in offer.findall("param"):
            param_name = (param.get("name") or "").strip().lower()
            if param_name in (
                "собівартість",
                "закупка",
                "закупочна ціна",
                "закупівельна ціна",
                "cost_price",
                "cost",
            ):
                if param.text and param.text.strip():
                    try:
                        return float(param.text.strip().replace(",", ".")), True
                    except ValueError:
                        pass

        # Fallback: price * 0.75 (default 25% margin)
        return round(price * 0.75, 2), False
