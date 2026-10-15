import json
import logging
from typing import Any, Optional
from google import genai
from google.genai import types

from src.config import settings

logger = logging.getLogger(__name__)


class GeminiMatcher:
    """Client for comparing products using Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model or "gemini-2.5-flash"
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def compare(
        self,
        our_title: str,
        our_sku: str,
        our_price: float,
        comp_title: str,
        comp_price: float,
    ) -> dict[str, Any]:
        """Compare our product and competitor's offer using Gemini with structured JSON output."""
        if not self.api_key or not self.client:
            return {
                "is_same_product": False,
                "confidence": 0.5,
                "reasoning": "Gemini API key not configured",
            }

        prompt = (
            "Ти експерт з товарного аналізу та e-commerce каталогів.\n"
            "Порівняй наступні два товари та визнач, чи це один і той самий продукт (однакова модель, бренд, ключові характеристики: ємність, потужність, роз'єми тощо).\n"
            "Дрібні відмінності в маркетингових назвах або наявності слів типу 'оригінал', 'новинка', 'гарантія' допускаються, якщо фізичний товар однаковий.\n"
            "Якщо є явна невідповідність (різна потужність W, різна ємність mAh, різна модель чи бренд) - це різні товари.\n\n"
            f"Наш товар: '{our_title}' (SKU: {our_sku}, ціна: {our_price} грн)\n"
            f"Товар конкурента: '{comp_title}' (ціна: {comp_price} грн)\n\n"
            "Поверни валідний JSON у наступному форматі:\n"
            "{\n"
            '  "is_same_product": boolean,\n'
            '  "confidence": float від 0.0 до 1.0,\n'
            '  "reasoning": "Коротке чітке обґрунтування українською мовою (1-2 речення)"\n'
            "}"
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text or "{}"
            data = json.loads(raw_text)

            is_same = bool(data.get("is_same_product", False))
            confidence = float(data.get("confidence", 0.5))
            reasoning = str(data.get("reasoning", "")).strip() or "Оцінка виконана моделлю Gemini."

            # Ensure confidence is clamped between 0.0 and 1.0
            confidence = max(0.0, min(1.0, confidence))

            return {
                "is_same_product": is_same,
                "confidence": round(confidence, 2),
                "reasoning": reasoning,
            }

        except Exception as exc:
            logger.warning(f"Error invoking GeminiMatcher: {exc}")
            return {
                "is_same_product": False,
                "confidence": 0.5,
                "reasoning": f"Помилка виклику AI: {exc}",
            }
