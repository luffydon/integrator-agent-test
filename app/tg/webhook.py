# app/tg/webhook.py
import os, re, json, time
from typing import Dict, Any, List, Tuple
from fastapi import APIRouter, HTTPException, Request
import aiohttp

# Your backend must expose: await backend_api.create_service(...)
try:
    from app.clients import backend_api as be
except Exception:
    be = None

from app.utils.telegram_client import TG

router = APIRouter()

# === Config ===
TG_SECRET = os.environ.get("TG_WEBHOOK_SECRET", "secret")  # set this!
INTEGRATOR_BASE_URL = (os.environ.get("INTEGRATOR_BASE_URL") or "http://localhost:8000").rstrip("/")
ADMIN_HEADER_NAME   = "X-Integrator-Admin"
ADMIN_HEADER_VALUE  = os.environ.get("PROMOTE_ADMIN_TOKEN", "")
MAX_ZIP_MB          = int(os.environ.get("MAX_ZIP_MB", "60"))
MAX_JSON_MB         = int(os.environ.get("MAX_JSON_MB", "5"))

# === Helpers ===
def _clean_json_comments(txt: str) -> str:
    # remove // comments and trailing commas
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

async def _post_integrator_stage_a(file_bytes: bytes, filename: str, title: str) -> Dict[str, Any]:
    endpoints = ["/integrator/stage-a/submit-zip", "/integrations/stage-a/submit-zip"]  # fallback for both spellings
    form = aiohttp.FormData()
    form.add_field("file", file_bytes, filename=filename, content_type="application/zip")
    form.add_field("title", title)
    headers = {ADMIN_HEADER_NAME: ADMIN_HEADER_VALUE} if ADMIN_HEADER_VALUE else {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300, connect=10, sock_read=240)) as s:
        last_404 = None
        for path in endpoints:
            url = f"{INTEGRATOR_BASE_URL}{path}"
            r = await s.post(url, data=form, headers=headers)
            if r.status == 404:
                last_404 = await r.text(); continue
            if r.status < 300:
                return await r.json()
            raise HTTPException(status_code=502, detail=f"Integrator Stage A error {r.status}: {await r.text()}")
        raise HTTPException(status_code=502, detail=f"Integrator Stage A 404 on all paths: {last_404}")

async def _post_integrator_promote(branch: str) -> Dict[str, Any]:
    endpoints = ["/integrator/stage-b/promote", "/integrations/stage-b/promote"]
    headers = {ADMIN_HEADER_NAME: ADMIN_HEADER_VALUE} if ADMIN_HEADER_VALUE else {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120, connect=10, sock_read=90)) as s:
        last_404 = None
        for path in endpoints:
            url = f"{INTEGRATOR_BASE_URL}{path}"
            r = await s.post(url, json={"branch": branch}, headers=headers)
            if r.status == 404:
                last_404 = await r.text(); continue
            if r.status < 300:
                return await r.json()
            raise HTTPException(status_code=502, detail=f"Integrator Stage B error {r.status}: {await r.text()}")
        raise HTTPException(status_code=502, detail=f"Integrator Stage B 404 on all paths: {last_404}")

async def _gh_headers():
    token = os.environ.get("INTEGRATOR_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="Missing GH token for revert (INTEGRATOR_GITHUB_TOKEN or GITHUB_TOKEN).")
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

async def _revert_previous_release():
    owner = os.environ.get("GITHUB_OWNER"); repo = os.environ.get("GITHUB_REPO")
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Set GITHUB_OWNER and GITHUB_REPO for revert.")
    api = "https://api.github.com"
    headers = await _gh_headers()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=10, sock_read=40)) as s:
        # 1) previous release tag
        r = await s.get(f"{api}/repos/{owner}/{repo}/releases?per_page=5", headers=headers)
        if r.status >= 300: raise HTTPException(status_code=502, detail=f"GH releases error {r.status}: {await r.text()}")
        rel = await r.json()
        if not rel or len(rel) < 2:
            raise HTTPException(status_code=400, detail="Not enough releases to revert.")
        tag = rel[1]["tag_name"]
        # 2) find Stage C workflow
        wf_name = os.environ.get("STAGE_C_WORKFLOW_NAME", "Stage C — Release & Verify")
        wf_file = os.environ.get("STAGE_C_WORKFLOW_FILE", "stage-c.yml")
        r = await s.get(f"{api}/repos/{owner}/{repo}/actions/workflows", headers=headers)
        if r.status >= 300: raise HTTPException(status_code=502, detail=f"GH workflows error {r.status}: {await r.text()}")
        data = await r.json()
        wf_id = None
        for w in data.get("workflows", []):
            if w.get("name") == wf_name or str(w.get("path","")).endswith(wf_file):
                wf_id = w["id"]; break
        if not wf_id:
            raise HTTPException(status_code=400, detail="Stage C workflow not found.")
        # 3) dispatch with inputs
        ref = os.environ.get("GIT_DEFAULT_REF", "main")
        payload = {"ref": ref, "inputs": {"tag": tag, "deploy_prod": "true"}}
        r = await s.post(f"{api}/repos/{owner}/{repo}/actions/workflows/{wf_id}/dispatches",
                         headers=headers, json=payload)
        if r.status not in (200, 201, 204):
            raise HTTPException(status_code=502, detail=f"GH dispatch error {r.status}: {await r.text()}")
    return tag

def _decode_bytes(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except Exception:
        return b.decode("utf-8", "ignore")

def _parse_services_from_json_text(text: str) -> List[Dict[str, Any]]:
    # Try plain JSON first
    try:
        data = json.loads(_clean_json_comments(text))
        items = _normalize_services(data)
        if items:
            return items
    except Exception:
        pass
    # Try NDJSON (one JSON object per line)
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

# === Telegram webhook ===
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

    # 1) Document uploads
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
        blob = await tg.download_file_by_path(fp)

        # a) ZIP → Stage A
        if file_name.endswith(".zip"):
            if file_size and file_size > MAX_ZIP_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ ZIP too large (> {MAX_ZIP_MB}MB)."); return {"ok": True}
            if len(blob) > MAX_ZIP_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ ZIP too large after download (> {MAX_ZIP_MB}MB)."); return {"ok": True}
            title = f"tg-{message.get('from',{}).get('username') or 'user'}-{int(time.time())}"
            try:
                result = await _post_integrator_stage_a(blob, file_name, title)
                branch = result.get("branch") or result.get("ref") or "(unknown)"
                await tg.send_message(chat_id, f"✅ Stage A uploaded\nBranch: {branch}")
            except HTTPException as e:
                await tg.send_message(chat_id, f"❌ Stage A failed: {e.detail}")
            return {"ok": True}

        # b) JSON / NDJSON → add service(s) from file (no wizard)
        if file_name.endswith(".json") or file_name.endswith(".ndjson"):
            if file_size and file_size > MAX_JSON_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ JSON too large (> {MAX_JSON_MB}MB)."); return {"ok": True}
            if len(blob) > MAX_JSON_MB * 1024 * 1024:
                await tg.send_message(chat_id, f"❌ JSON too large after download (> {MAX_JSON_MB}MB)."); return {"ok": True}
            if be is None:
                await tg.send_message(chat_id, "❌ Backend API not available (app.clients.backend_api)."); return {"ok": True}
            text = _decode_bytes(blob)
            items = _parse_services_from_json_text(text)
            if not items:
                await tg.send_message(chat_id, "❌ No valid services found in the JSON file."); return {"ok": True}
            uid = str(message.get("from",{}).get("id") or chat_id)
            ok, lines = await _create_services(items, uid)
            body = "\n".join(lines[:12])
            if len(lines) > 12:
                body += f"\n… and {len(lines)-12} more."
            await tg.send_message(chat_id, f"Created {ok}/{len(items)} services (from file):\n{body}")
            return {"ok": True}

        # other docs ignored
        return {"ok": True}

    # 2) Text commands
    text = (message.get("text") or "").strip()

    # /promote stage-a/<branch>
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

    # /revert (previous release)
    if text.startswith("/revert"):
        try:
            tag = await _revert_previous_release()
            await tg.send_message(chat_id, f"🔁 Revert started to tag: {tag}. Check GitHub Actions.")
        except HTTPException as e:
            await tg.send_message(chat_id, f"❌ Revert failed: {e.detail}")
        return {"ok": True}

    # add service(s) in text (no wizard)
    m = re.match(r"^\s*add\s+services?\s*:\s*(\{.*|\[.*)", text, re.IGNORECASE | re.DOTALL)
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

    # default hint
    await tg.send_message(chat_id, "Send a .zip (Stage A), /promote stage-a/<branch>, /revert, or attach services.json/.ndjson.")
    return {"ok": True}
