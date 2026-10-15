from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re
import time
from typing import Callable, Optional
from sqlalchemy.orm import Session

from src.database.models import CompetitorOffer, Product, ProductMatch
from src.services.prom_scraper import PromScraper

logger = logging.getLogger(__name__)


@dataclass
class ProductDiscoveryResult:
    """Detailed summary of competitor discovery for a single product."""

    product: Product
    query: str
    found_count: int
    saved_count: int
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    offers: list[dict] = field(default_factory=list)


class DiscoveryService:
    """Orchestrator for discovering competitor offers on Prom.ua for catalog products."""

    def __init__(self, scraper: Optional[PromScraper] = None) -> None:
        self.scraper = scraper or PromScraper()

    @staticmethod
    def clean_title(title: str) -> str:
        """Strip brackets, quotes, and redundant punctuation from title."""
        cleaned = re.sub(r"[\(\)\[\]\{\}\"\'«»]", " ", title)
        return " ".join(cleaned.split())

    def build_search_query(self, product: Product) -> str:
        """Construct the most appropriate search query for a product."""
        if product.sku and len(product.sku.strip()) >= 3:
            return product.sku.strip()
        return self.clean_title(product.title)

    def discover_product_detailed(
        self,
        db: Session,
        product: Product,
        max_offers: int = 5,
    ) -> ProductDiscoveryResult:
        """Search competitors and upsert into database with detailed metadata."""
        query = self.build_search_query(product)
        offers = self.scraper.search(query, max_results=max_offers)

        # Fallback to cleaned title if SKU returned no offers
        if not offers and product.sku and product.title:
            fallback_query = self.clean_title(product.title)
            if fallback_query != query:
                fallback_offers = self.scraper.search(fallback_query, max_results=max_offers)
                if fallback_offers:
                    offers = fallback_offers
                    query = fallback_query

        saved_count = 0
        prices: list[float] = []

        for offer_data in offers:
            url = offer_data["url"]
            price = offer_data["price"]
            prices.append(price)

            existing = db.query(CompetitorOffer).filter_by(url=url).first()
            if existing:
                existing.price = price
                existing.is_in_stock = offer_data["is_in_stock"]
                existing.scraped_at = datetime.now(timezone.utc)
                if offer_data.get("title"):
                    existing.title = offer_data["title"]
                if offer_data.get("seller_name"):
                    existing.seller_name = offer_data["seller_name"]
                if offer_data.get("image_url"):
                    existing.image_url = offer_data["image_url"]
                if offer_data.get("external_id"):
                    existing.external_id = offer_data["external_id"]
                offer_obj = existing
                saved_count += 1
            else:
                new_offer = CompetitorOffer(
                    source=offer_data.get("source", "prom.ua"),
                    external_id=offer_data.get("external_id"),
                    title=offer_data["title"],
                    price=price,
                    seller_name=offer_data.get("seller_name"),
                    url=url,
                    image_url=offer_data.get("image_url"),
                    is_in_stock=offer_data["is_in_stock"],
                    scraped_at=datetime.now(timezone.utc),
                )
                db.add(new_offer)
                db.flush()
                offer_obj = new_offer
                saved_count += 1

            # Ensure ProductMatch link exists
            match_link = (
                db.query(ProductMatch)
                .filter_by(product_id=product.id, competitor_offer_id=offer_obj.id)
                .first()
            )
            if not match_link:
                new_match = ProductMatch(
                    product_id=product.id,
                    competitor_offer_id=offer_obj.id,
                    match_method="discovered",
                    confidence_score=0.0,
                    status="pending",
                )
                db.add(new_match)

        db.commit()

        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None

        return ProductDiscoveryResult(
            product=product,
            query=query,
            found_count=len(offers),
            saved_count=saved_count,
            min_price=min_price,
            max_price=max_price,
            offers=offers,
        )

    def discover_for_product(
        self,
        db: Session,
        product: Product,
        max_offers: int = 5,
    ) -> int:
        """Find competitor offers for a product, upsert into DB, and return count."""
        result = self.discover_product_detailed(db, product, max_offers=max_offers)
        return result.saved_count

    def discover_all(
        self,
        db: Session,
        limit_products: Optional[int] = None,
        offers_per_product: int = 5,
        delay_seconds: float = 1.0,
        on_progress: Optional[Callable[[int, int, ProductDiscoveryResult], None]] = None,
    ) -> list[ProductDiscoveryResult]:
        """Iterate over active products, scrape competitors, and persist them."""
        query = db.query(Product).filter(Product.is_active == True).order_by(Product.id)  # noqa: E712
        if limit_products is not None and limit_products > 0:
            query = query.limit(limit_products)

        products = query.all()
        total_products = len(products)
        results: list[ProductDiscoveryResult] = []

        for idx, product in enumerate(products, start=1):
            res = self.discover_product_detailed(
                db,
                product,
                max_offers=offers_per_product,
            )
            results.append(res)

            if on_progress:
                on_progress(idx, total_products, res)

            # Polite delay between requests to protect against rate limits
            if idx < total_products and delay_seconds > 0:
                time.sleep(delay_seconds)

        return results
