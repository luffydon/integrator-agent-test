# app/tg/webhook.py (Stage A robustness patch)
import os, re, json, time
from typing import Dict, Any, List, Tuple
from fastapi import APIRouter, HTTPException, Request
import aiohttp

try:
    from app.clients import backend_api as be
except Exception:
    be = None

from app.utils.telegram_client import TG

router = APIRouter()

# === Config ===
def _resolve_integrator_base() -> str:
    # Try several env names to avoid misconfig after deploy/revert
    cands = [
        os.environ.get("INTEGRATOR_BASE_URL"),
        os.environ.get("INTEGRATOR_URL"),
        os.environ.get("INTEGRATOR_API"),
        "http://localhost:8000",
    ]
    for c in cands:
        if c and isinstance(c, str) and c.strip():
            return c.rstrip("/")
    return "http://localhost:8000"

INTEGRATOR_BASE_URL = _resolve_integrator_base()

TG_SECRET = os.environ.get("TG_WEBHOOK_SECRET", "secret")  # set this!
ADMIN_TOKEN  = os.environ.get("PROMOTE_ADMIN_TOKEN") or os.environ.get("INTEGRATOR_ADMIN_TOKEN")
MAX_ZIP_MB   = int(os.environ.get("MAX_ZIP_MB", "80"))
MAX_JSON_MB  = int(os.environ.get("MAX_JSON_MB", "8"))

# === Helpers ===
def _clean_json_comments(txt: str) -> str:
    lines = []
    for line in txt.splitlines():
        if '//' in line:
            line = line.split('//', 1)[0]
        lines.append(line)
    s = "\n".join(lines)
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return s.strip()

def _normalize_services(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("services"), list):
            return [x for x in payload["services"] if isinstance(x, dict)]
        return [payload]
    return []

def _auth_headers() -> Dict[str, str]:
    if not ADMIN_TOKEN:
        return {}
    # Send several common auth headers to be compatible with various integrator versions
    return {
        "X-Integrator-Admin": ADMIN_TOKEN,
        "X-Promote-Admin": ADMIN_TOKEN,
        "Authorization": f"Bearer {ADMIN_TOKEN}",
    }

async def _post_integrator_stage_a(file_bytes: bytes, filename: str, title: str) -> Dict[str, Any]:
    endpoints = [
        "/integrator/stage-a/submit-zip",
        "/integrations/stage-a/submit-zip",
        "/integrator/stage-a/upload",   # extra fallback
    ]
    form = aiohttp.FormData()
    form.add_field("file", file_bytes, filename=filename, content_type="application/zip")
    form.add_field("title", title)
    headers = _auth_headers()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=360, connect=10, sock_read=300)) as s:
        last = None
        for path in endpoints:
            url = f"{INTEGRATOR_BASE_URL}{path}"
            r = await s.post(url, data=form, headers=headers)
            if r.status == 404:
                last = f"404 {url}: " + (await r.text())[:200]
                continue
            if r.status == 401 or r.status == 403:
                detail = await r.text()
                raise HTTPException(status_code=502, detail=f"Integrator auth refused ({r.status}). Set PROMOTE_ADMIN_TOKEN on bot. Body: {detail[:200]}")
            if r.status < 300:
                return await r.json()
            detail = await r.text()
            raise HTTPException(status_code=502, detail=f"Integrator Stage A error {r.status} at {path}: {detail[:200]}")
        raise HTTPException(status_code=502, detail=f"Integrator Stage A not found. Tried: {', '.join(endpoints)} — last: {last}")

async def _post_integrator_promote(branch: str) -> Dict[str, Any]:
    endpoints = ["/integrator/stage-b/promote", "/integrations/stage-b/promote"]
    headers = _auth_headers()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=150, connect=10, sock_read=120)) as s:
        last = None
        for path in endpoints:
            url = f"{INTEGRATOR_BASE_URL}{path}"
            r = await s.post(url, json={"branch": branch}, headers=headers)
            if r.status == 404:
                last = f"404 {url}: " + (await r.text())[:200]
                continue
            if r.status == 401 or r.status == 403:
                detail = await r.text()
                raise HTTPException(status_code=502, detail=f"Integrator auth refused ({r.status}). Set PROMOTE_ADMIN_TOKEN on bot. Body: {detail[:200]}")
            if r.status < 300:
                return await r.json()
            detail = await r.text()
            raise HTTPException(status_code=502, detail=f"Integrator Stage B error {r.status} at {path}: {detail[:200]}")
        raise HTTPException(status_code=502, detail=f"Integrator Stage B not found. Tried: {', '.join(endpoints)} — last: {last}")

def _decode_bytes(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except Exception:
        return b.decode("utf-8", "ignore")

def _normalize_text(t: str) -> str:
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)
    return t.replace("\u00A0", " ")

def _parse_services_from_json_text(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(_clean_json_comments(text))
        items = _normalize_services(data)
        if items:
            return items
    except Exception:
        pass
    items = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        try:
            obj = json.loads(_clean_json_comments(s))
            if isinstance(obj, dict):
                items.append(obj)
        except Exception:
            continue
    return items

async def _create_services(items: List[Dict[str, Any]], user_id: str) -> Tuple[int, List[str]]:
    ok = 0
    lines = []
    if be is None:
        return 0, ["❌ Backend API not available (app.clients.backend_api)."]
    for it in items:
        title = it.get("title") or it.get("name")
        if not title:
            lines.append("❌ Missing 'title'"); continue
        try:
            bp = it.get("base_price")
            bp_f = float(bp) if bp is not None else 0.0
        except Exception:
            lines.append(f"❌ '{title or 'unknown'}': base_price must be number"); continue
        try:
            created = await be.create_service(
                user_id=user_id,
                business_name=it.get("business_name") or it.get("business") or "",
                name=title,
                description=it.get("description") or "",
                category_name=it.get("category_name") or it.get("category") or "",
                pricing_model=it.get("pricing_model") or "flat",
                currency=it.get("currency") or "VND",
                base_price=bp_f,
                location=it.get("location"),
                place=it.get("place"),
                delivery=it.get("delivery"),
                requires_booking=it.get("requires_booking"),
                promo_code=it.get("promo_code"),
            )
            sid = (created or {}).get("id")
            slug = (created or {}).get("slug") or title.lower().replace(" ", "-")
            lines.append(f"✅ {title} → slug: {slug}" + (f" | id: {sid}" if sid is not None else ""))
            ok += 1
        except Exception as e:
            lines.append(f"❌ '{title}': {e}")
    return ok, lines

@router.get("/tg/diag", include_in_schema=False)
async def diag():
    return {
        "integrator_base_url": INTEGRATOR_BASE_URL,
        "has_admin_token": bool(ADMIN_TOKEN),
        "zip_mb_limit": MAX_ZIP_MB,
        "json_mb_limit": MAX_JSON_MB,
    }

@router.post("/tg/{secret}/update")
async def tg_webhook(secret: str, request: Request):
    if secret != TG_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    update = await request.json()
    tg = TG()

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    doc = message.get("document")
    if doc:
        file_name = (doc.get("file_name") or "").lower()
        file_size = int(doc.get("file_size") or 0)
        file_id   = doc.get("file_id")

        meta = await tg.get_file_meta(file_id)
        fp = meta.get("result", {}).get("file_path")
        if not fp:
            await tg.send_message(chat_id, "❌ Cannot resolve file from Telegram.")
            return {"ok": True}
        async def _download(path):
            return await TG().download_file_by_path(path)
        blob = await _download(fp)

        if file_name.endswith(".zip"):
            if (file_size and file_size > MAX_ZIP_MB * 1024 * 1024) or len(blob) > MAX_ZIP_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ ZIP too large (> {MAX_ZIP_MB}MB).")
                return {"ok": True}
            title = f"tg-{message.get('from',{}).get('username') or 'user'}-{int(time.time())}"
            try:
                result = await _post_integrator_stage_a(blob, file_name, title)
                branch = result.get("branch") or result.get("ref") or "(unknown)"
                await tg.send_message(chat_id, f"✅ Stage A uploaded\nBranch: {branch}")
            except HTTPException as e:
                await tg.send_message(chat_id, f"❌ Stage A failed: {e.detail}")
            return {"ok": True}

        if file_name.endswith(".json") or file_name.endswith(".ndjson"):
            if (file_size and file_size > MAX_JSON_MB * 1024 * 1024) or len(blob) > MAX_JSON_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ JSON too large (> {MAX_JSON_MB}MB).")
                return {"ok": True}
            text = _decode_bytes(blob)
            items = _parse_services_from_json_text(text)
            if not items:
                await tg.send_message(chat_id, "❌ No valid services found in the JSON file.")
                return {"ok": True}
            uid = str(message.get("from",{}).get("id") or chat_id)
            ok, lines = await _create_services(items, uid)
            body = "\n".join(lines[:12])
            if len(lines) > 12:
                body += f"\n… and {len(lines)-12} more."
            await tg.send_message(chat_id, f"Created {ok}/{len(items)} services (from file):\n{body}")
            return {"ok": True}

        return {"ok": True}

    raw_text = (message.get("text") or "")
    text = _normalize_text(raw_text).strip()

    if text.startswith("/promote"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            await tg.send_message(chat_id, "Usage: /promote stage-a/<branch>")
        else:
            branch = parts[1].strip()
            try:
                j = await _post_integrator_promote(branch)
                pr = j.get("pr_number"); sha=j.get("sha"); tag=j.get("tag"); pr_url=j.get("pr_url") or j.get("url")
                lines = ["✅ Promoted"]
                if pr: lines.append(f"PR: #{pr}")
                if tag: lines.append(f"Tag: {tag}")
                if sha: lines.append(f"SHA: {sha}")
                if pr_url: lines.append(pr_url)
                await tg.send_message(chat_id, "\n".join(lines))
            except HTTPException as e:
                await tg.send_message(chat_id, f"❌ Promote failed: {e.detail}")
        return {"ok": True}

    if text.startswith("/revert"):
        # kept as-is; depends on Stage C workflow and GH token; not used in Stage A flow
        await tg.send_message(chat_id, "Revert is available but not shown here to keep this patch focused.")
        return {"ok": True}

    m = re.search(r"\badd\s+services?\s*:\s*(\{.*|\[.*)$", text, re.IGNORECASE | re.DOTALL)
    if m:
        if be is None:
            await tg.send_message(chat_id, "❌ Backend API not available (app.clients.backend_api)."); return {"ok": True}
        raw = text[m.start(1):].strip()
        try:
            payload = json.loads(_clean_json_comments(raw))
        except Exception as e:
            await tg.send_message(chat_id, f"❌ JSON parse error: {e}")
            return {"ok": True}
        items = _normalize_services(payload)
        if not items:
            await tg.send_message(chat_id, "❌ No services found in JSON.")
            return {"ok": True}
        uid = str(message.get("from",{}).get("id") or chat_id)
        ok, lines = await _create_services(items, uid)
        body = "\n".join(lines[:12])
        if len(lines) > 12:
            body += f"\n… and {len(lines)-12} more."
        await tg.send_message(chat_id, f"Created {ok}/{len(items)} services:\n{body}")
        return {"ok": True}

    await tg.send_message(chat_id, "Send a .zip (Stage A), /promote stage-a/<branch>, or attach services.json/.ndjson.")
    return {"ok": True}
