# app/telegram/render.py
from __future__ import annotations
import html, re
from typing import Dict, List, Tuple

URL_RE = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)

def _escape(s: str) -> str:
    return html.escape(s or "", quote=True)

def extract_links(text: str) -> Tuple[str, List[str]]:
    if not text:
        return "", []
    links = URL_RE.findall(text)
    return text, links

def label_for_link(url: str) -> str:
    u = url.lower()
    if u.startswith("https://t.me/") or u.startswith("https://telegram.me/"):
        return "Open in Telegram"
    return "Open link"

def render_service_card(item: Dict) -> str:
    # Do NOT show IDs; show only user-facing info
    title = item.get("title") or item.get("name") or "Untitled"
    desc = item.get("description") or ""
    location = item.get("location") or item.get("address") or ""
    hours = item.get("hours") or item.get("opening_hours") or ""
    price_hint = item.get("price_hint") or ""
    promo = item.get("promo_code") or ""

    desc_text, links = extract_links(desc)

    lines: List[str] = []
    lines.append(f"<b>{_escape(title)}</b>")
    if desc_text:
        lines.append(_escape(desc_text))
    if location:
        lines.append(f"📍 {_escape(location)}")
    if hours:
        lines.append(f"🕒 {_escape(hours)}")
    if price_hint:
        lines.append(f"💲 {_escape(price_hint)}")
    if promo:
        lines.append(f"🎁 Use promo code <b>{_escape(promo)}</b> to get 10% off!")

    for url in links:
        label = label_for_link(url)
        safe_url = _escape(url)
        lines.append(f'🔗 <a href="{safe_url}">{_escape(label)}</a>')

    return "\n".join(lines)