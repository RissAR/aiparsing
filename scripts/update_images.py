import logging
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.connection import SessionLocal
from src.database.models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Verified, working Prom.ua image URLs for sample catalog
SKU_IMAGE_MAP = {
    "PB-BASEUS-100W": "https://images.prom.ua/3993730294_w200_h200_umb-portativnoe-zaryadnoe.jpg",
    "PPDGL-01": "https://images.prom.ua/3993730294_w200_h200_umb-portativnoe-zaryadnoe.jpg",
    "VXN4285GL": "https://images.prom.ua/6064249628_w200_h200_originalnyj-xiaomi-redmi.jpg",
    "C80A-WHT": "https://images.prom.ua/6992579052_w200_h200_setevoe-zaryadnoe-ustrojstvo.jpg",
    "CCGP120201": "https://images.prom.ua/4320161993_w200_h200_moschnoe-zaryadnoe-ustrojstvo.jpg",
    "MHJE3ZM/A": "https://images.prom.ua/6105299939_w200_h200_zaryadnoe-ustrojstvo-apple.jpg",
    "CATLKLF-G1": "https://images.prom.ua/6163233091_w200_h200_kabel-baseus-cafule.jpg",
    "CAWJ000001": "https://images.prom.ua/6088180105_w200_h200_kabel-baseus-tungsten.jpg",
    "X20-TC-2M": "https://images.prom.ua/3803855350_w200_h200_kabel-hoco-x20.jpg",
    "NGTW140001": "https://images.prom.ua/7190860600_w200_h200_besprovodnye-naushniki-baseus.jpg",
    "BHR6992GL": "https://images.prom.ua/6470418130_w200_h200_besprovodnye-naushniki-xiaomi.jpg",
    "MTJV3TY/A": "https://images.prom.ua/7087039187_w200_h200_naushniki-apple-mtjv3tya.jpg",
    "C40151300111-00": "https://images.prom.ua/6708988066_w200_h200_derzhatel-v-avto.jpg",
}

# Mapping for prom_feed.xml offer IDs
OFFER_ID_IMAGE_MAP = {
    "1001": "https://images.prom.ua/3993730294_w200_h200_umb-portativnoe-zaryadnoe.jpg",
    "1002": "https://images.prom.ua/6064249628_w200_h200_originalnyj-xiaomi-redmi.jpg",
    "1003": "https://images.prom.ua/6992579052_w200_h200_setevoe-zaryadnoe-ustrojstvo.jpg",
    "1004": "https://images.prom.ua/4320161993_w200_h200_moschnoe-zaryadnoe-ustrojstvo.jpg",
    "1005": "https://images.prom.ua/6105299939_w200_h200_zaryadnoe-ustrojstvo-apple.jpg",
    "1006": "https://images.prom.ua/6163233091_w200_h200_kabel-baseus-cafule.jpg",
    "1007": "https://images.prom.ua/6088180105_w200_h200_kabel-baseus-tungsten.jpg",
    "1008": "https://images.prom.ua/3803855350_w200_h200_kabel-hoco-x20.jpg",
    "1009": "https://images.prom.ua/7190860600_w200_h200_besprovodnye-naushniki-baseus.jpg",
    "1010": "https://images.prom.ua/6470418130_w200_h200_besprovodnye-naushniki-xiaomi.jpg",
    "1011": "https://images.prom.ua/7087039187_w200_h200_naushniki-apple-mtjv3tya.jpg",
    "1012": "https://images.prom.ua/6708988066_w200_h200_derzhatel-v-avto.jpg",
}


def update_database_images() -> int:
    """Update products table with working image URLs."""
    db = SessionLocal()
    updated_count = 0
    try:
        products = db.query(Product).all()
        for p in products:
            new_img = SKU_IMAGE_MAP.get(p.sku)
            if new_img and p.image_url != new_img:
                p.image_url = new_img
                updated_count += 1
                logger.info(f"Updated product {p.id} ({p.sku}) image to: {new_img}")
        db.commit()
    finally:
        db.close()
    return updated_count


def update_prom_feed_xml() -> int:
    """Update data/samples/prom_feed.xml with working image URLs."""
    feed_path = Path(__file__).resolve().parent.parent / "data" / "samples" / "prom_feed.xml"
    if not feed_path.exists():
        logger.warning(f"Feed file not found: {feed_path}")
        return 0

    tree = ET.parse(feed_path)
    root = tree.getroot()
    updated_count = 0

    for offer in root.findall(".//offer"):
        offer_id = offer.get("id")
        picture_elem = offer.find("picture")
        if offer_id in OFFER_ID_IMAGE_MAP and picture_elem is not None:
            new_img = OFFER_ID_IMAGE_MAP[offer_id]
            picture_elem.text = new_img
            updated_count += 1
            logger.info(f"Updated offer {offer_id} picture in XML to: {new_img}")

    tree.write(feed_path, encoding="UTF-8", xml_declaration=True)
    return updated_count


def main() -> None:
    logger.info("Starting image updates...")
    db_updated = update_database_images()
    xml_updated = update_prom_feed_xml()
    logger.info(f"Done! DB products updated: {db_updated}, XML offers updated: {xml_updated}")


if __name__ == "__main__":
    main()
