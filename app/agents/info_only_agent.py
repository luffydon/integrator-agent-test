# app/agents/info_only_agent.py

from __future__ import annotations
from typing import List, Dict, Tuple, Protocol
from app.telegram.render import render_service_card
from app.telegram.ui import build_categories_keyboard
from app.intent.recognizer import recognize_intent
from app.clients import backend_api as be

# In-memory pagination per chat (simple and good enough here)
_PAGINATION: Dict[str, Dict] = {}
ITEM_PAGE_SIZE = 5

def _set_page(chat_id: str, category: str, offset: int) -> None:
    _PAGINATION[chat_id] = {"category": category, "offset": offset}

def _get_page(chat_id: str) -> Tuple[str, int]:
    st = _PAGINATION.get(chat_id) or {}
    return st.get("category", ""), int(st.get("offset", 0))

class TelegramSender(Protocol):
    async def send_message(self, chat_id: str, text: str, reply_markup: dict|None=None,
                           parse_mode: str|None=None, disable_web_page_preview: bool|None=None,
                           reply_to_message_id: int|None=None) -> bool: ...

async def handle_message(chat_id: str, text: str, telegram: TelegramSender):
    intent = recognize_intent(text)

    if intent["type"] == "add_service":
        return {"handled": True, "output": "Okay, let’s add a service. Send JSON or follow the prompts."}

    if intent["type"] == "info_only_notice":
        return {"handled": True, "output": "Currently we only provide information. Booking isn’t available."}

    if intent["type"] == "show_categories":
        cats = await be.get_non_empty_categories_async()
        if not cats:
            return {"handled": True, "output": "Nothing available right now."}
        kb = build_categories_keyboard(cats, page=0)
        await telegram.send_message(chat_id, "Available categories:", reply_markup=kb)
        return {"handled": True, "output": None}

    if intent["type"] == "browse_category":
        cat = intent.get("category") or ""
        items = await be.list_services_by_category_async(cat)
        if not items:
            return {"handled": True, "output": "Nothing available right now."}
        _set_page(chat_id, cat, 0)
        return await _send_items_page(chat_id, items, 0, telegram)

    # Fallback → show categories
    cats = await be.get_non_empty_categories_async()
    if not cats:
        return {"handled": True, "output": "Nothing available right now."}
    kb = build_categories_keyboard(cats, page=0)
    await telegram.send_message(chat_id, "Available categories:", reply_markup=kb)
    return {"handled": True, "output": None}

async def handle_callback(chat_id: str, user_id: str, data: str, telegram: TelegramSender):
    # Category navigator
    if data.startswith("CATNAV:"):
        _, kind, page_s = data.split(":")
        page = int(page_s)
        cats = await be.get_non_empty_categories_async()
        kb = build_categories_keyboard(cats, page=page)
        await telegram.send_message(chat_id, "Available categories:", reply_markup=kb)
        return {"handled": True, "output": None}

    # Category selected
    if data.startswith("CAT:"):
        parts = data.split(":")
        category = parts[1]
        items = await be.list_services_by_category_async(category)
        if not items:
            await telegram.send_message(chat_id, "Nothing available in this category right now.")
            return {"handled": True, "output": None}
        _set_page(chat_id, category, 0)
        return await _send_items_page(chat_id, items, 0, telegram)

    # Items pagination
    if data == "ITEMS:MORE":
        category, offset = _get_page(chat_id)
        if not category:
            return {"handled": True, "output": "Nothing available right now."}
        items = await be.list_services_by_category_async(category)
        return await _send_items_page(chat_id, items, offset, telegram)

    return {"handled": False, "output": None}

async def _send_items_page(chat_id: str, items: List[Dict], offset: int, telegram: TelegramSender):
    end = min(offset + ITEM_PAGE_SIZE, len(items))
    page_items = items[offset:end]
    for it in page_items:
        msg = render_service_card(it)
        await telegram.send_message(
            chat_id,
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    if end < len(items):
        next_offset = end
        _set_page(chat_id, _get_page(chat_id)[0], next_offset)
        await telegram.send_message(
            chat_id,
            "Show more?",
            reply_markup={"inline_keyboard": [[{"text": "Show more", "callback_data": "ITEMS:MORE"}]]}
        )
    return {"handled": True, "output": None}