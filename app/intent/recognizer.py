# app/intent/recognizer.py
# =========================================
# FULL FILE — Simplified and corrected logic
# =========================================

def recognize_intent(text: str) -> dict:
    t = (text or "").strip().lower()
    if not t:
        return {"type": "unknown"}

    # Explicit commands first
    if t in ("menu", "/menu", "/start", "categories", "what do you have", "what services do you have"):
        return {"type": "show_categories"}
    
    if any(kw in t for kw in ["add service", "create service"]):
        return {"type": "add_service"}

    # If the text is a single word without spaces or slashes,
    # it's treated as a category browse request. This is the logic
    # that will correctly handle "/tech" after it's processed
    # by the webhook.
    if " " not in t and "/" not in t:
        return {"type": "browse_category", "category": t}

    # Hardcoded keywords for multi-word phrases
    if any(w in t for w in ["food", "restaurant", "eat"]):
        return {"type": "browse_category", "category": "food"}
    if any(w in t for w in ["transport", "taxi", "bike"]):
        return {"type": "browse_category", "category": "transport"}
    if "tech" in t:
        return {"type": "browse_category", "category": "tech"}
    
    # Fallback for more complex phrases
    # if any(w in t for w in ["book", "reserve", "delivery", "now or later"]):
    #     return {"type": "info_only_notice"}

    return {"type": "unknown"}