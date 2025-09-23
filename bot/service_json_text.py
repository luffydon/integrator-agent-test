import os, re, json, time, aiohttp
from aiogram import types
from aiogram.dispatcher import Dispatcher

MAX_SERVICE_JSON_BYTES = int(os.environ.get("MAX_SERVICE_JSON_BYTES", "512000"))

_TRIG = re.compile(r'^\s*(add\s*service|service\s*add|add\s*svc)\s*:?\s*\{', re.I | re.S)
_SLUG_RE = re.compile(r"[^a-z0-9._-]+")

def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", str(name).strip().lower()).strip("-")
    return (slug or f"svc-{int(time.time())}")[:60]

def _get(d, path):
    cur = d
    for key in path.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur

def _derive_service_slug(payload: dict) -> str:
    candidates = [
        _get(payload, "name"),
        _get(payload, "service.name"),
        _get(payload, "metadata.name"),
        _get(payload, "id"),
        _get(payload, "title"),
        _get(payload, "business_name"),
    ]
    for c in candidates:
        if c:
            return _slugify(str(c))
    return _slugify("svc")

def _extract_json_from_text(text: str) -> str:
    s = text.replace("\u00a0", " ").strip()
    if _TRIG.search(s):
        i, j = s.find("{"), s.rfind("}")
        if i == -1 or j == -1 or j < i:
            raise ValueError("No JSON object found")
        s = s[i:j+1]
    if "{" in s and "}" in s:
        i, j = s.find("{"), s.rfind("}")
        s = s[i:j+1]
    s = re.sub(r"//.*", "", s)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return s.strip()

def wire_service_json_text(dp: Dispatcher, bot_token: str):
    @dp.message_handler(content_types=["text"])
    async def handle_service_text(message: types.Message):
        txt = message.text or ""
        if "{" not in txt or "}" not in txt:
            return
        try:
            raw = _extract_json_from_text(txt)
            if len(raw.encode("utf-8")) > MAX_SERVICE_JSON_BYTES:
                await message.reply("❌ JSON too large.")
                return
            payload = json.loads(raw)
        except Exception:
            return

        if not isinstance(payload, dict):
            return

        slug = _derive_service_slug(payload)
        await message.reply(
            "✅ Service detected (no prompts)\n"
            f"service: `{slug}`",
            parse_mode="Markdown",
        )
        from aiogram import types as _t
        raise _t.CancelHandler()
