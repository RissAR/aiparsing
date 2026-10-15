from pathlib import Path
from lxml import etree
from sqlalchemy.orm import Session

from src.database.models import Product


class FeedExporter:
    """Service for generating Prom.ua compliant YML/XML catalog feeds with updated prices."""

    @classmethod
    def generate_xml(cls, db: Session) -> str:
        """Generate valid Prom.ua YML/XML string with current catalog prices."""
        products = (
            db.query(Product)
            .filter(Product.is_active == True)  # noqa: E712
            .order_by(Product.id)
            .all()
        )

        root = etree.Element("yml_catalog")
        shop = etree.SubElement(root, "shop")

        name = etree.SubElement(shop, "name")
        name.text = "Мій Магазин (AI Repriced)"

        currencies = etree.SubElement(shop, "currencies")
        etree.SubElement(currencies, "currency", id="UAH", rate="1")

        categories = etree.SubElement(shop, "categories")
        etree.SubElement(categories, "category", id="1").text = "Електроніка та аксесуари"

        offers = etree.SubElement(shop, "offers")

        for p in products:
            offer = etree.SubElement(offers, "offer", id=str(p.id), available="true")
            etree.SubElement(offer, "name").text = p.title
            if p.sku:
                etree.SubElement(offer, "vendorCode").text = p.sku
            etree.SubElement(offer, "price").text = f"{p.current_price:.2f}"
            etree.SubElement(offer, "currencyId").text = "UAH"
            etree.SubElement(offer, "categoryId").text = "1"
            if p.image_url:
                etree.SubElement(offer, "picture").text = p.image_url

        xml_bytes = etree.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
            pretty_print=True,
        )
        return xml_bytes.decode("utf-8")

    @classmethod
    def save_to_file(
        cls,
        db: Session,
        filepath: str = "data/exports/prom_updated_feed.xml",
    ) -> str:
        """Generate and save YML/XML feed to disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        xml_content = cls.generate_xml(db)
        path.write_text(xml_content, encoding="utf-8")
        return str(path)
