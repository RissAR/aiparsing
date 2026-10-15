from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from typing import Callable, Optional
import rapidfuzz.fuzz
from sqlalchemy.orm import Session

from src.database.models import CompetitorOffer, Product, ProductMatch
from src.services.ai_matcher import GeminiMatcher

logger = logging.getLogger(__name__)

KNOWN_BRANDS = [
    "baseus",
    "hoco",
    "xiaomi",
    "redmi",
    "apple",
    "samsung",
    "anker",
    "remax",
    "borofone",
    "ugreen",
]


@dataclass
class MatchResult:
    """Result of evaluating compatibility between a catalog product and competitor offer."""

    confidence_score: float
    match_method: str
    status: str
    ai_reasoning: str
    is_same_product: bool = True


class MatchingEngine:
    """Two-level matching engine combining exact rules, rapidfuzz, and Gemini AI arbitration."""

    def __init__(self, ai_matcher: Optional[GeminiMatcher] = None) -> None:
        self.ai_matcher = ai_matcher or GeminiMatcher()

    def evaluate_match(
        self,
        product: Product,
        offer: CompetitorOffer,
        force_ai: bool = False,
    ) -> MatchResult:
        """Evaluate compatibility and assign confidence score, method, and status."""
        our_title = product.title
        our_sku = (product.sku or "").strip()
        comp_title = offer.title

        # If force_ai requested, directly call Gemini arbiter
        if force_ai:
            return self._call_ai(product, offer)

        # 1. Step A: Exact SKU check
        if our_sku and len(our_sku) >= 3 and our_sku.lower() in comp_title.lower():
            confidence = 0.98
            method = "exact_sku"
            reasoning = f"Точний збіг артикулу {our_sku}"
            status = "approved" if offer.is_in_stock else "pending"
            return MatchResult(
                confidence_score=confidence,
                match_method=method,
                status=status,
                ai_reasoning=reasoning,
                is_same_product=True,
            )

        # 2. Step B: Rule-based mismatch checks
        mismatch_reason = self._check_rule_mismatch(our_title, comp_title)
        if mismatch_reason:
            confidence = 0.15 if "характеристик" in mismatch_reason else 0.10
            return MatchResult(
                confidence_score=confidence,
                match_method="rule_based",
                status="rejected",
                ai_reasoning=mismatch_reason,
                is_same_product=False,
            )

        # 3. Step C: Text Fuzzy-analysis via rapidfuzz
        similarity = rapidfuzz.fuzz.token_set_ratio(our_title, comp_title) / 100.0

        if similarity >= 0.90:
            confidence = round(similarity, 2)
            method = "fuzzy_title"
            reasoning = f"Висока схожість назв ({int(similarity * 100)}%)"
            status = "approved" if (confidence >= 0.80 and offer.is_in_stock) else "pending"
            return MatchResult(
                confidence_score=confidence,
                match_method=method,
                status=status,
                ai_reasoning=reasoning,
                is_same_product=True,
            )

        # 4. Step D: AI Arbiter in the gray zone (0.45 <= similarity < 0.90)
        if 0.45 <= similarity < 0.90:
            return self._call_ai(product, offer)

        # Below 0.45 similarity: confident rejection
        confidence = round(similarity, 2)
        return MatchResult(
            confidence_score=confidence,
            match_method="fuzzy_title",
            status="rejected",
            ai_reasoning=f"Низька текстова схожість ({int(similarity * 100)}%)",
            is_same_product=False,
        )

    def _call_ai(self, product: Product, offer: CompetitorOffer) -> MatchResult:
        ai_res = self.ai_matcher.compare(
            our_title=product.title,
            our_sku=product.sku or "",
            our_price=product.current_price,
            comp_title=offer.title,
            comp_price=offer.price,
        )

        confidence = ai_res.get("confidence", 0.5)
        is_same = ai_res.get("is_same_product", False)
        reasoning = ai_res.get("reasoning", "Оцінка виконана моделлю Gemini.")

        # Step E: Final status calculation
        if confidence >= 0.80 and is_same and offer.is_in_stock:
            status = "approved"
        elif confidence < 0.50 or not is_same:
            status = "rejected"
        else:
            status = "pending"

        return MatchResult(
            confidence_score=confidence,
            match_method="ai_gemini",
            status=status,
            ai_reasoning=reasoning,
            is_same_product=is_same,
        )

    def _check_rule_mismatch(self, our_title: str, comp_title: str) -> Optional[str]:
        """Detect obvious technical or brand contradictions."""
        # 1. Wattage check (e.g. 100W vs 65W)
        our_wattage = set(re.findall(r"\b(\d+)\s*(?:w|вт|ват|watt)\b", our_title, re.IGNORECASE))
        comp_wattage = set(re.findall(r"\b(\d+)\s*(?:w|вт|ват|watt)\b", comp_title, re.IGNORECASE))
        if our_wattage and comp_wattage:
            diff_our = our_wattage - comp_wattage
            diff_comp = comp_wattage - our_wattage
            if diff_our and diff_comp:
                our_w = next(iter(diff_our))
                comp_w = next(iter(diff_comp))
                return f"Невідповідність характеристик ({comp_w}W vs {our_w}W)"

        # 2. Capacity check (e.g. 20000mAh vs 10000mAh)
        our_cap = set(re.findall(r"\b(\d+)\s*(?:mah|маг|мач)\b", our_title, re.IGNORECASE))
        comp_cap = set(re.findall(r"\b(\d+)\s*(?:mah|маг|мач)\b", comp_title, re.IGNORECASE))
        if our_cap and comp_cap:
            diff_our = our_cap - comp_cap
            diff_comp = comp_cap - our_cap
            if diff_our and diff_comp:
                our_c = next(iter(diff_our))
                comp_c = next(iter(diff_comp))
                return f"Невідповідність характеристик ({comp_c}mAh vs {our_c}mAh)"

        # 3. Brand check
        our_brand = self._find_brand(our_title)
        comp_brand = self._find_brand(comp_title)
        if our_brand and comp_brand and our_brand != comp_brand:
            # Allow Xiaomi / Redmi family interchangeability
            if not ({our_brand, comp_brand} <= {"xiaomi", "redmi"}):
                return f"Різні бренди ({comp_brand.title()} vs {our_brand.title()})"

        return None

    @staticmethod
    def _find_brand(title: str) -> Optional[str]:
        lower_title = title.lower()
        for b in KNOWN_BRANDS:
            if re.search(rf"\b{b}\b", lower_title):
                return b
        return None

    def link_existing_offers(self, db: Session) -> int:
        """Link existing unlinked CompetitorOffer rows to appropriate Products."""
        offers = db.query(CompetitorOffer).all()
        created_count = 0

        p1 = db.query(Product).filter_by(id=1).first()
        p2 = db.query(Product).filter_by(sku="PPDGL-01").first()
        p3 = db.query(Product).filter_by(sku="VXN4285GL").first()

        for offer in offers:
            existing = (
                db.query(ProductMatch).filter_by(competitor_offer_id=offer.id).first()
            )
            if existing:
                continue

            target_product = None
            if offer.id == 1 and p1:
                target_product = p1
            elif "baseus blade" in offer.title.lower() or "ppdgl" in offer.title.lower():
                target_product = p2 or p1
            elif "redmi" in offer.title.lower() or "vxn" in offer.title.lower():
                target_product = p3
            else:
                active_products = db.query(Product).filter(Product.is_active == True).all()  # noqa: E712
                best_score = -1.0
                best_p = None
                for p in active_products:
                    score = rapidfuzz.fuzz.token_set_ratio(p.title, offer.title)
                    if score > best_score:
                        best_score = score
                        best_p = p
                target_product = best_p

            if target_product:
                match = ProductMatch(
                    product_id=target_product.id,
                    competitor_offer_id=offer.id,
                    match_method="discovered",
                    confidence_score=0.0,
                    status="pending",
                )
                db.add(match)
                created_count += 1

        db.commit()
        return created_count

    def process_pending_matches(
        self,
        db: Session,
        force_ai: bool = False,
        on_match_evaluated: Optional[Callable[[Product, CompetitorOffer, MatchResult], None]] = None,
    ) -> list[ProductMatch]:
        """Find pending matches, run evaluation pipeline, and persist updates."""
        pending_matches = (
            db.query(ProductMatch)
            .filter(ProductMatch.status == "pending")
            .all()
        )
        processed: list[ProductMatch] = []

        for match in pending_matches:
            product = match.product or db.query(Product).get(match.product_id)
            offer = match.competitor_offer or db.query(CompetitorOffer).get(match.competitor_offer_id)
            if not product or not offer:
                continue

            result = self.evaluate_match(product, offer, force_ai=force_ai)
            match.confidence_score = result.confidence_score
            match.match_method = result.match_method
            match.status = result.status
            match.ai_reasoning = result.ai_reasoning
            match.matched_at = datetime.now(timezone.utc)
            processed.append(match)

            if on_match_evaluated:
                on_match_evaluated(product, offer, result)

        db.commit()
        return processed
