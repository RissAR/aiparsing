from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.database.connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    current_price = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    min_margin_percent = Column(Float, default=15.0, nullable=False)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True)

    # Relationships
    matches = relationship("ProductMatch", back_populates="product", cascade="all, delete-orphan")
    price_recommendations = relationship(
        "PriceRecommendation", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', title='{self.title[:30]}')>"


class CompetitorOffer(Base):
    __tablename__ = "competitor_offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, default="prom.ua", nullable=False)
    external_id = Column(String, nullable=True, index=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    seller_name = Column(String, nullable=True)
    url = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    is_in_stock = Column(Boolean, default=True, nullable=False)
    scraped_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    matches = relationship(
        "ProductMatch", back_populates="competitor_offer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CompetitorOffer(id={self.id}, source='{self.source}', price={self.price})>"


class ProductMatch(Base):
    __tablename__ = "product_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    competitor_offer_id = Column(
        Integer, ForeignKey("competitor_offers.id"), index=True, nullable=False
    )
    match_method = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    status = Column(String, default="pending", nullable=False)
    ai_reasoning = Column(Text, nullable=True)
    matched_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="matches")
    competitor_offer = relationship("CompetitorOffer", back_populates="matches")

    def __repr__(self) -> str:
        return (
            f"<ProductMatch(id={self.id}, product_id={self.product_id}, "
            f"competitor_offer_id={self.competitor_offer_id}, status='{self.status}')>"
        )


class PriceRecommendation(Base):
    __tablename__ = "price_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True, nullable=False)
    current_price = Column(Float, nullable=False)
    min_market_price = Column(Float, nullable=False)
    recommended_price = Column(Float, nullable=False)
    status = Column(String, default="pending", nullable=False)
    calculated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="price_recommendations")

    def __repr__(self) -> str:
        return (
            f"<PriceRecommendation(id={self.id}, product_id={self.product_id}, "
            f"recommended_price={self.recommended_price}, status='{self.status}')>"
        )
