# app/bot/tg_add_service_direct.py
# Direct add of one or many services from JSON text, skipping any wizard.

import re
import json
from typing import Any, Dict, List, Tuple
from aiogram import types
from aiogram.dispatcher import Dispatcher

from app.clients import backend_api as be  # uses your existing create_service()

# Accepts lines starting with:  add service:  OR  add services:
_PREFIX_RE = re.compile(r"^\s*add\s+services?\s*:\s*(\{.*|\[.*)", re.IGNORECASE | re.DOTALL)

def _strip_json_comments(s: str) -> str:
    # remove // line comments; also strip trailing commas before } or ]
    lines = []
    for line in s.splitlines():
        if '//' in line:
            line = line.split('//', 1)[0]
        lines.append(line)
    txt = "\n".join(lines)
    txt = re.sub(r",\s*([}\]])", r"\1", txt)
    return txt.strip()

def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or "service"

def _coalesce(d: Dict[str, Any], *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default

def _normalize_payloads(raw: Any) -> List[Dict[str, Any]]:
    """
    Accepts:
      - dict (single service)
      - list[dict] (many services)
      - dict{"services": list[dict]} (many services)
    Returns list[dict].
    """
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        if isinstance(raw.get("services"), list):
            return [x for x in raw["services"] if isinstance(x, dict)]
        return [raw]
    return []

async def _create_one(user_id: str, item: Dict[str, Any]) -> Tuple[bool, str]:
    title = _coalesce(item, "title", "name")
    if not title:
        return False, "❌ Missing 'title'"

    business_name   = _coalesce(item, "business_name", "business", default="")
    category_name   = _coalesce(item, "category_name", "category", default="")
    pricing_model   = _coalesce(item, "pricing_model", default="flat")
    currency        = _coalesce(item, "currency", default="VND")
    description     = _coalesce(item, "description", default="")
    location        = _coalesce(item, "location", default=None)
    promo_code      = item.get("promo_code")
    place           = item.get("place")
    delivery        = item.get("delivery")
    requires_booking= item.get("requires_booking")

    base_price = item.get("base_price")
    try:
        base_price_f = float(base_price) if base_price is not None else 0.0
    except Exception:
        return False, f"❌ '{title}': base_price must be a number"

    try:
        created = await be.create_service(
            user_id=user_id,
            business_name=business_name,
            name=title,
            description=description,
            category_name=category_name,
            pricing_model=pricing_model,
            currency=currency,
            base_price=base_price_f,
            location=location,
            place=place,
            delivery=delivery,
            requires_booking=requires_booking,
            promo_code=promo_code,
        )
    except Exception as e:
        return False, f"❌ '{title}': {e}"

    slug = (created or {}).get("slug") or _slugify(title)
    sid  = (created or {}).get("id")
    id_part = f" | id: {sid}" if sid is not None else ""
    return True, f"✅ {title} → slug: {slug}{id_part}"

def wire_add_service_direct(dp: Dispatcher, *, require_prefix: bool = True) -> None:
    """
    Registers a text handler that catches messages starting with:
      add service:{...JSON...}
      add services:[{...}, {...}]  or  add services:{ "services":[...] }
    and creates services directly (no wizard).
    """
    @dp.message_handler(content_types=["text'])
    async def _handle(message: types.Message):
        text = (message.text or "")
        m = _PREFIX_RE.match(text) if require_prefix else _PREFIX_RE.search(text)
        if not m:
            return

        json_blob = text[m.start(1):].strip()
        try:
            payload = json.loads(_strip_json_comments(json_blob))
        except Exception as e:
            await message.reply(f"❌ Could not parse JSON: {e}")
            return

        items = _normalize_payloads(payload)
        if not items:
            await message.reply("❌ No services found in JSON (expect object, array, or {services:[...]}).")
            return

        user_id = str(message.from_user.id)
        lines: List[str] = []
        ok = 0
        for item in items:
            ok1, msg = await _create_one(user_id, item)
            if ok1: ok += 1
            lines.append(msg)

        MAX_LINES = 12
        body = "\n".join(lines[:MAX_LINES])
        if len(lines) > MAX_LINES:
            body += f"\n… and {len(lines) - MAX_LINES} more."
        await message.reply(f"Created {ok}/{len(items)} services:\n{body}")
