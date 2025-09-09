# app/clients/catalog_api.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from app.clients import backend_api as be

STRICT = os.getenv("CATALOG_STRICT", "1") != "0"  # default strict ON

def _norm_category_key(c: Any) -> str:
    if isinstance(c, dict):
        return c.get("key") or c.get("name") or ""
    return str(c or "").strip()

class CatalogAPI:
    @staticmethod
    def get_non_empty_categories() -> List[str]:
        # Use backend hook if present
        if hasattr(be, "get_non_empty_categories"):
            cats = be.get_non_empty_categories()
            # normalize to list[str]
            out = sorted({_norm_category_key(c) for c in (cats or []) if _norm_category_key(c)})
            return out

        # Strict mode: fail loudly so you don’t think it’s working when it’s not
        if STRICT:
            raise RuntimeError("backend_api.get_non_empty_categories() is missing. Implement it.")
        # Dev-only fallback
        return ["food", "transport"]

    @staticmethod
    def list_services_by_category(category_key: str) -> List[Dict]:
        if hasattr(be, "list_services_by_category"):
            return be.list_services_by_category(category_key)

        if STRICT:
            raise RuntimeError("backend_api.list_services_by_category() is missing. Implement it.")
        # Dev-only fallback
        if category_key == "food":
            return [
                {"name": "Pizza Place", "description": "Best slices. https://t.me/pizzaplace_bot", "price_hint": "$$", "promo_code": "SLICE10"},
                {"name": "Sushi Bar", "description": "Fresh nigiri.", "price_hint": "$$$"},
                {"name": "Burger Truck", "description": "Smash burgers at the park."},
                {"name": "Pasta Corner", "description": "Homemade pasta daily."},
                {"name": "Vegan Deli", "description": "Plant-based goodies."},
                {"name": "Curry House", "description": "Spicy!"},
            ]
        if category_key == "transport":
            return [
                {"name": "City Taxi", "description": "Call a cab. https://example.com/taxi"},
                {"name": "Bike Rentals", "description": "Hourly rentals near you."},
            ]
        return []
