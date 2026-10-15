from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Optional
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.models import CompetitorOffer, PriceRecommendation, Product, ProductMatch
from src.services.discovery_service import DiscoveryService
from src.services.feed_exporter import FeedExporter
from src.services.matching_engine import MatchingEngine
from src.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"

app = FastAPI(
    title="AI Repricer for Prom.ua",
    description="Автоматизована система моніторингу цін, AI-зіставлення та динамічного репрайсингу",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static asset routes
@app.get("/", response_class=FileResponse)
async def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json", response_class=FileResponse)
async def serve_manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/sw.js", response_class=FileResponse)
async def serve_sw() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


# 1. Stats Endpoint
@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    total_products = db.query(Product).filter(Product.is_active == True).count()  # noqa: E712
    total_offers = db.query(CompetitorOffer).count()
    approved_matches = db.query(ProductMatch).filter_by(status="approved").count()
    applied_recommendations = (
        db.query(PriceRecommendation).filter_by(status="applied").count()
    )

    # Calculate potential profit boost from active recommendations
    products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
    potential_profit_boost = 0.0

    for p in products:
        rec = (
            db.query(PriceRecommendation)
            .filter_by(product_id=p.id)
            .order_by(PriceRecommendation.id.desc())
            .first()
        )
        if rec and rec.recommended_price > rec.current_price:
            potential_profit_boost += rec.recommended_price - rec.current_price

    return {
        "total_products": total_products,
        "total_offers": total_offers,
        "approved_matches": approved_matches,
        "applied_recommendations": applied_recommendations,
        "potential_profit_boost": round(potential_profit_boost, 2),
    }


# 2. Products List Endpoint
@app.get("/api/products")
def get_products(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    products = (
        db.query(Product)
        .filter(Product.is_active == True)  # noqa: E712
        .order_by(Product.id)
        .all()
    )

    result = []
    for p in products:
        # Fetch related matches and competitor offers
        matches = (
            db.query(ProductMatch)
            .join(CompetitorOffer, ProductMatch.competitor_offer_id == CompetitorOffer.id)
            .filter(ProductMatch.product_id == p.id)
            .all()
        )

        competitors = []
        best_match = None
        for m in matches:
            offer = m.competitor_offer
            competitors.append(
                {
                    "offer_id": offer.id,
                    "title": offer.title,
                    "seller_name": offer.seller_name or "Невідомий продавець",
                    "price": offer.price,
                    "url": offer.url,
                    "image_url": offer.image_url,
                    "is_in_stock": offer.is_in_stock,
                    "match_status": m.status,
                    "confidence_score": m.confidence_score,
                    "match_method": m.match_method,
                    "ai_reasoning": m.ai_reasoning,
                }
            )
            if not best_match or (m.status == "approved" and best_match.status != "approved"):
                best_match = m
            elif m.confidence_score > best_match.confidence_score:
                best_match = m

        # Latest recommendation
        rec = (
            db.query(PriceRecommendation)
            .filter_by(product_id=p.id)
            .order_by(PriceRecommendation.id.desc())
            .first()
        )

        rec_data = None
        if rec:
            rec_data = {
                "id": rec.id,
                "current_price": rec.current_price,
                "min_market_price": rec.min_market_price,
                "recommended_price": rec.recommended_price,
                "status": rec.status,
                "price_diff": round(rec.recommended_price - p.current_price, 2),
            }

        result.append(
            {
                "id": p.id,
                "sku": p.sku,
                "title": p.title,
                "category": p.category,
                "current_price": p.current_price,
                "cost_price": p.cost_price,
                "min_margin_percent": p.min_margin_percent,
                "floor_price": round(
                    p.cost_price * (1.0 + (p.min_margin_percent or 15.0) / 100.0), 2
                ),
                "image_url": p.image_url,
                "competitors": competitors,
                "match_summary": (
                    {
                        "status": best_match.status,
                        "confidence_score": best_match.confidence_score,
                        "match_method": best_match.match_method,
                        "ai_reasoning": best_match.ai_reasoning,
                    }
                    if best_match
                    else None
                ),
                "recommendation": rec_data,
            }
        )

    return result


# 3. Action Endpoints
@app.post("/api/actions/run-all")
def run_all(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run full autopilot cycle: Discovery -> Matching -> Repricing."""
    try:
        # Step 1: Discover competitors for active products
        discovery_svc = DiscoveryService()
        discovery_svc.discover_all(db, limit_products=None, offers_per_product=5, delay_seconds=0.5)

        # Step 2: Match products
        matching_engine = MatchingEngine()
        matching_engine.link_existing_offers(db)
        processed_matches = matching_engine.process_pending_matches(db, force_ai=False)

        # Step 3: Reprice
        pricing_engine = PricingEngine()
        recs = pricing_engine.calculate_all(db, delta=5.0)

        return {
            "status": "success",
            "message": "Повний цикл автопілоту завершено",
            "matches_processed": len(processed_matches),
            "recommendations_generated": len(recs),
        }
    except Exception as exc:
        logger.exception("Error during run-all action")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/actions/discover")
def run_discovery(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        service = DiscoveryService()
        results = service.discover_all(db, limit_products=None, offers_per_product=5, delay_seconds=0.5)
        total_found = sum(r.saved_count for r in results)
        return {
            "status": "success",
            "message": f"Збір конкурентів завершено. Збережено оферів: {total_found}",
            "offers_saved": total_found,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/actions/match")
def run_match(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        engine = MatchingEngine()
        engine.link_existing_offers(db)
        processed = engine.process_pending_matches(db, force_ai=False)
        return {
            "status": "success",
            "message": f"AI-зіставлення завершено. Оброблено кандидатів: {len(processed)}",
            "processed_count": len(processed),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/actions/reprice")
def run_reprice(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        engine = PricingEngine()
        recs = engine.calculate_all(db, delta=5.0)
        return {
            "status": "success",
            "message": f"Перерахунок цін завершено. Згенеровано рекомендацій: {len(recs)}",
            "recalculated_count": len(recs),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/actions/apply/{product_id}")
def apply_single_price(product_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    rec = (
        db.query(PriceRecommendation)
        .filter_by(product_id=product_id, status="pending")
        .order_by(PriceRecommendation.id.desc())
        .first()
    )
    if not rec:
        # Check if there is an existing recommendation
        rec = (
            db.query(PriceRecommendation)
            .filter_by(product_id=product_id)
            .order_by(PriceRecommendation.id.desc())
            .first()
        )
        if not rec:
            raise HTTPException(
                status_code=404,
                detail=f"Не знайдено рекомендацій для товару ID {product_id}",
            )

    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")

    product.current_price = rec.recommended_price
    product.updated_at = datetime.now(timezone.utc)
    rec.status = "applied"
    db.commit()

    return {
        "status": "success",
        "message": f"Ціну для товару '{product.title}' оновлено на {product.current_price} грн",
        "product_id": product.id,
        "new_price": product.current_price,
    }


@app.post("/api/actions/apply-all")
def apply_all_prices(db: Session = Depends(get_db)) -> dict[str, Any]:
    engine = PricingEngine()
    applied_count = engine.apply_recommendations(db)
    return {
        "status": "success",
        "message": f"Успішно застосовано рекомендацій: {applied_count}",
        "applied_count": applied_count,
    }


# 4. XML Feed Export Endpoint
@app.get("/api/export/feed.xml")
def export_feed(db: Session = Depends(get_db)) -> Response:
    xml_content = FeedExporter.generate_xml(db)
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": "inline; filename=prom_updated_feed.xml"},
    )


# Mount static directory for any static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
