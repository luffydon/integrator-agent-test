# app/clients/backend_api.py
# =========================================
# FULL FILE — improved category + listing logic
# =========================================
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ---- Config ----
BASE = os.getenv("SERVICE_API_BASE", "").rstrip("/")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "")
TIMEOUT = float(os.getenv("SERVICE_API_TIMEOUT", "12"))

CATEGORY_NAME_TO_ID = {
    "food": 1,
    "sim card": 2,
    "real estate": 3,
    "surf": 4,
    "sport": 5,
    "tourism": 6,
    "tech": 7,
}

# ---- JWT helpers ----
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _sign_hs256(payload: Dict[str, Any]) -> str:
    if not SECRET_KEY:
        raise RuntimeError("APP_SECRET_KEY is not set in .env file")
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def _auth_headers(user_id: Optional[str]) -> Dict[str, str]:
    if not BASE:
        raise RuntimeError("SERVICE_API_BASE is not set in .env file")
    now = int(time.time())
    token = _sign_hs256({"user_id": user_id or "router-service", "iat": now, "exp": now + 3600})
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

# ---- HTTP helpers (async) ----
async def _get(path: str, params: Optional[Dict[str, Any]], user_id: Optional[str]):
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        headers = _auth_headers(user_id)
        r = await cx.get(f"{BASE}{path}", params=params, headers=headers)
        r.raise_for_status()
        return r.json()

async def _post(path: str, json_body: Dict[str, Any], user_id: Optional[str]):
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        headers = _auth_headers(user_id)
        r = await cx.post(f"{BASE}{path}", json=json_body, headers=headers)
        r.raise_for_status()
        return r.json()

# ---- HTTP helpers (sync) for info-only agent ----
def _get_sync(path: str, params: Optional[Dict[str, Any]], user_id: Optional[str]) -> Any:
    headers = _auth_headers(user_id)
    with httpx.Client(timeout=TIMEOUT) as cx:
        r = cx.get(f"{BASE}{path}", params=params, headers=headers)
        r.raise_for_status()
        return r.json()

# ---- Normalizers ----
def _normalize_services_payload(data: Any) -> List[Dict[str, Any]]:
    """
    Accepts either a list or dict with 'results'/ 'items'.
    Returns a list[dict].
    """
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return [x for x in data["results"] if isinstance(x, dict)]
        if "items" in data and isinstance(data["items"], list):
            return [x for x in data["items"] if isinstance(x, dict)]
    return []

def _extract_category_name(svc: Dict[str, Any], cat_map: Dict[int, str]) -> Tuple[Optional[str], Optional[int]]:
    """
    Try to pull a human-readable category name; also return id if present.
    """
    name = (svc.get("category") or svc.get("type") or svc.get("category_name"))
    cid = svc.get("category_id")
    # If we have only id, map to name
    if not name and isinstance(cid, int):
        name = cat_map.get(cid)
    # Clean up
    if isinstance(name, str):
        name = name.strip()
    return (name if name else None), (cid if isinstance(cid, int) else None)

# ---- Optional: build a category map from /api/service-categories/ ----
async def _categories_map_async(user_id: Optional[str]) -> Dict[int, str]:
    try:
        data = await _get("/api/service-categories/", None, user_id)
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("categories") or data.get("results") or data.get("items") or []
        out: Dict[int, str] = {}
        for c in items:
            if not isinstance(c, dict):
                continue
            cid = c.get("id")
            nm = c.get("name") or c.get("label") or c.get("key")
            if isinstance(cid, int) and isinstance(nm, str) and nm.strip():
                out[cid] = nm.strip()
        return out
    except Exception:
        return {}

# =========================================
# PUBLIC: async calls (your existing API)
# =========================================
async def list_services(user_id: Optional[str] = None, query: Optional[str] = None):
    params = {"q": query} if query else None
    return await _get("/api/services/", params, user_id)

async def list_categories(user_id: Optional[str] = None):
    try:
        data = await _get("/api/service-categories/", None, user_id)
        if isinstance(data, dict) and "categories" in data:
            return data
        if isinstance(data, list):
            return {"categories": data}
    except Exception:
        pass
    try:
        services = await _get("/api/services/", None, user_id) or []
        items = _normalize_services_payload(services)
        names = sorted({
            (svc.get("category") or svc.get("type") or svc.get("category_name") or "").strip()
            for svc in items
            if (svc.get("category") or svc.get("type") or svc.get("category_name"))
        })
        return {"categories": [{"name": n} for n in names if n]}
    except Exception as e:
        return {"error": str(e)}

async def create_booking(
    user_id: str,
    service_id: str,
    full_name: str,
    scheduled_at: str,
    duration: Optional[int] = None,
):
    payload: Dict[str, Any] = {"service_id": service_id, "full_name": full_name, "scheduled_at": scheduled_at}
    if duration:
        payload["duration"] = duration
    return await _post("/api/bookings/", payload, user_id)

async def create_service(
    user_id: str,
    business_name: str,
    name: str,
    description: str,
    category_name: str,
    pricing_model: str,
    currency: str,
    base_price: float,
    location: Optional[str] = None,
    place: Optional[bool] = None,
    delivery: Optional[bool] = None,
    requires_booking: Optional[bool] = None,
    time_unit: Optional[str] = None,
    min_duration: Optional[int] = None,
    max_duration: Optional[int] = None,
    attributes: Optional[Dict[str, Any]] = None,
):
    category_id = CATEGORY_NAME_TO_ID.get((category_name or "").lower())
    if category_id is None:
        return {"error": f"Category '{category_name}' not found."}
    payload: Dict[str, Any] = {
        "business_name": business_name,
        "name": name,
        "description": description,
        "category_id": category_id,
        "pricing_model": pricing_model,
        "currency": currency,
        "base_price": base_price,
        "location": location,
        "place": place,
        "delivery": delivery,
        "requires_booking": requires_booking,
        "time_unit": time_unit,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "attributes": attributes or {},
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    return await _post("/api/services/", payload, user_id)

# =========================================
# PUBLIC: ASYNC hooks for info-only agent
# =========================================

# --- Start Correction ---
async def list_services_by_category_async(category_key: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Robustly fetches all services and filters them by category on the client side.
    """
    if not category_key:
        return []
    
    try:
        # 1. Fetch all services
        data = await _get("/api/services/", None, user_id)
        items = _normalize_services_payload(data)
        if not items:
            return []

        # 2. Build a map of category IDs to names for matching
        cat_map = await _categories_map_async(user_id)

        # 3. Filter the full list
        filtered: List[Dict[str, Any]] = []
        for svc in items:
            name, _ = _extract_category_name(svc, cat_map)
            if name and name.lower().strip() == category_key.lower().strip():
                filtered.append(svc)
        
        return filtered

    except Exception as e:
        print(f"[ERROR] list_services_by_category_async failed: {e}")
        return []
# --- End Correction ---

async def get_non_empty_categories_async(user_id: Optional[str] = None) -> List[str]:
    try:
        data = await _get("/api/services/", None, user_id)
    except Exception:
        return []
    items = _normalize_services_payload(data)
    if not items:
        return []
    cat_map = await _categories_map_async(user_id)
    names: set[str] = set()
    for svc in items:
        name, _ = _extract_category_name(svc, cat_map)
        if name:
            names.add(name)
    return sorted(names)