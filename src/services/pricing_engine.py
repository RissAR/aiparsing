from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from src.database.models import CompetitorOffer, PriceRecommendation, Product, ProductMatch


@dataclass
class CalculationDetail:
    """Detailed metadata for price recommendation calculation."""

    product: Product
    recommendation: PriceRecommendation
    floor_price: float
    approved_offers_count: int
    min_market_price: float
    target_price: float
    is_floor_applied: bool


class PricingEngine:
    """Dynamic repricing engine with margin protection and market-following logic."""

    def calculate_for_product_detailed(
        self,
        db: Session,
        product: Product,
        delta: float = 5.0,
    ) -> CalculationDetail:
        """Calculate market-based price recommendation with margin floor protection."""
        # 1. Fetch valid approved competitors in stock with price > 0
        approved_offers = (
            db.query(CompetitorOffer)
            .join(ProductMatch, ProductMatch.competitor_offer_id == CompetitorOffer.id)
            .filter(
                ProductMatch.product_id == product.id,
                ProductMatch.status == "approved",
                CompetitorOffer.is_in_stock == True,  # noqa: E712
                CompetitorOffer.price > 0,
            )
            .all()
        )

        # 2. Floor price calculation: cost_price * (1.0 + min_margin_percent / 100.0)
        margin_percent = product.min_margin_percent if product.min_margin_percent is not None else 15.0
        floor_price = round(product.cost_price * (1.0 + margin_percent / 100.0), 2)

        # 3. Scenarios for recommended price determination
        if not approved_offers:
            min_market_price = round(product.current_price, 2)
            target_price = min_market_price
            recommended_price = min_market_price
            is_floor_applied = False
        else:
            competitor_prices = [o.price for o in approved_offers]
            min_market_price = round(min(competitor_prices), 2)
            target_price = round(min_market_price - delta, 2)
            recommended_price = round(max(target_price, floor_price), 2)
            is_floor_applied = target_price < floor_price

        # 4. Save recommendation to database
        rec = PriceRecommendation(
            product_id=product.id,
            current_price=product.current_price,
            min_market_price=min_market_price,
            recommended_price=recommended_price,
            status="pending",
            calculated_at=datetime.now(timezone.utc),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        return CalculationDetail(
            product=product,
            recommendation=rec,
            floor_price=floor_price,
            approved_offers_count=len(approved_offers),
            min_market_price=min_market_price,
            target_price=target_price,
            is_floor_applied=is_floor_applied,
        )

    def calculate_for_product(
        self,
        db: Session,
        product: Product,
        delta: float = 5.0,
    ) -> PriceRecommendation:
        """Calculate and persist price recommendation for a single product."""
        detail = self.calculate_for_product_detailed(db, product, delta=delta)
        return detail.recommendation

    def calculate_all(
        self,
        db: Session,
        delta: float = 5.0,
    ) -> list[PriceRecommendation]:
        """Calculate and persist price recommendations for all active products."""
        active_products = (
            db.query(Product)
            .filter(Product.is_active == True)  # noqa: E712
            .order_by(Product.id)
            .all()
        )
        recommendations = []
        for product in active_products:
            rec = self.calculate_for_product(db, product, delta=delta)
            recommendations.append(rec)
        return recommendations

    def calculate_all_detailed(
        self,
        db: Session,
        delta: float = 5.0,
    ) -> list[CalculationDetail]:
        """Calculate detailed recommendations for all active products."""
        active_products = (
            db.query(Product)
            .filter(Product.is_active == True)  # noqa: E712
            .order_by(Product.id)
            .all()
        )
        details = []
        for product in active_products:
            detail = self.calculate_for_product_detailed(db, product, delta=delta)
            details.append(detail)
        return details

    def apply_recommendations(
        self,
        db: Session,
        recommendation_ids: Optional[list[int]] = None,
    ) -> int:
        """Apply recommended prices to catalog products and mark recommendations as applied."""
        query = db.query(PriceRecommendation).filter(PriceRecommendation.status == "pending")
        if recommendation_ids is not None:
            query = query.filter(PriceRecommendation.id.in_(recommendation_ids))

        pending_recs = query.all()
        applied_count = 0

        for rec in pending_recs:
            product = db.query(Product).get(rec.product_id)
            if product:
                product.current_price = rec.recommended_price
                product.updated_at = datetime.now(timezone.utc)
                rec.status = "applied"
                applied_count += 1

        db.commit()
        return applied_count
