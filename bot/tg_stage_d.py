# bot/tg_stage_d.py
import os, aiohttp, time, json, re
from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext

INTEGRATOR_BASE_URL = os.environ.get("INTEGRATOR_BASE_URL", "http://localhost:8000")
ADMIN_HEADER_NAME   = "X-Integrator-Admin"
ADMIN_HEADER_VALUE  = os.environ.get("PROMOTE_ADMIN_TOKEN", "")
MAX_BYTES           = int(os.environ.get("MAX_EDIT_UPLOAD_BYTES", str(500 * 1024)))

_SLUG_RE = re.compile(r"[^a-z0-9._-]+")
_WIRED = False

def _derive_service_slug(payload: dict, filename: str) -> str:
    name = None
    if isinstance(payload, dict):
        name = (
            payload.get("name")
            or (payload.get("service") or {}).get("name")
            or (payload.get("metadata") or {}).get("name")
            or payload.get("id")
        )
    if not name:
        base = os.path.splitext(os.path.basename(filename or ""))[0]
        name = base or f"svc-{int(time.time())}"
    slug = _SLUG_RE.sub("-", str(name).strip().lower()).strip("-")
    return (slug or f"svc-{int(time.time())}")[:60]

def wire_stage_d(dp: Dispatcher, bot_token: str):
    global _WIRED
    if _WIRED:
        return
    _WIRED = True

    @dp.message_handler(content_types=["document"], state="*")
    async def handle_docs(message: types.Message, state: FSMContext):
        # ensure uploads handled even if stuck in a state
        if await state.get_state():
            await state.finish()

        doc = message.document
        name = (doc.file_name or "").lower()
        if not any(name.endswith(ext) for ext in (".patch", ".diff", ".yaml", ".yml", ".json")):
            return

        # Download
        try:
            file = await dp.bot.get_file(doc.file_id)
            tg_url = f"https://api.telegram.org/file/bot{bot_token}/{file.file_path}"
            timeout = aiohttp.ClientTimeout(total=180, connect=10, sock_read=120)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(tg_url) as r:
                    r.raise_for_status()
                    data = await r.read()
        except Exception as e:
            await message.reply(f"❌ Failed to download file: {e}")
            return

        if len(data) > MAX_BYTES:
            await message.reply("❌ File too large (max 500KB).")
            return

        headers = {ADMIN_HEADER_NAME: ADMIN_HEADER_VALUE} if ADMIN_HEADER_VALUE else {}
        title = f"tg-{message.from_user.username or 'user'}-{int(time.time())}"
        dry = bool(message.caption and "dryrun" in message.caption.lower())

        # PATCH
        if name.endswith(('.patch', '.diff')):
            try:
                url = f"{INTEGRATOR_BASE_URL}/integrations/stage-d/{'dry-run' if dry else 'submit-patch'}"
                form = aiohttp.FormData()
                form.add_field("file", data, filename=doc.file_name, content_type="text/x-diff")
                form.add_field("title", title)
                if dry: form.add_field("kind", "patch")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180, connect=10, sock_read=120)) as sess:
                    async with sess.post(url, data=form, headers=headers) as resp:
                        if resp.status < 300:
                            j = await resp.json()
                            files = j.get("files", [])
                            await message.reply(f"✅ Patch {'(dry-run) ' if dry else ''}ok\nBranch: {j.get('branch')}\nFiles: {', '.join(files) if files else '(none)'}")
                        else:
                            await message.reply(f"❌ Patch error {resp.status}.")
            except Exception as e:
                await message.reply(f"❌ Patch failed: {e}")
            return

        # JSON service: auto create services/<slug>/service.json (no prompts)
        if name.endswith('.json'):
            try:
                payload = json.loads(data.decode('utf-8'))
            except Exception:
                await message.reply("❌ Invalid JSON.")
                return

            svc = _derive_service_slug(payload, doc.file_name)
            spec = {
                "edits": [{
                    "op": "file.create",
                    "path": f"services/{svc}/service.json",
                    "content": json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                }]
            }
            try:
                url = f"{INTEGRATOR_BASE_URL}/integrations/stage-d/{'dry-run' if dry else 'submit-edits'}"
                form = aiohttp.FormData()
                form.add_field("file", json.dumps(spec).encode("utf-8"), filename="edit.json", content_type="application/json")
                form.add_field("title", f"service-{svc}")
                if dry: form.add_field("kind", "edits")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180, connect=10, sock_read=120)) as sess:
                    async with sess.post(url, data=form, headers=headers) as resp:
                        if resp.status < 300:
                            j = await resp.json()
                            files = j.get("files", [])
                            await message.reply(f"✅ Service '{svc}' {'(dry-run) ' if dry else ''}applied\nBranch: {j.get('branch')}\nFiles: {', '.join(files) if files else '(none)'}")
                        else:
                            await message.reply(f"❌ Service apply error {resp.status}.")
            except Exception as e:
                await message.reply(f"❌ Service apply failed: {e}")
            return

        # YAML/other spec
        try:
            url = f"{INTEGRATOR_BASE_URL}/integrations/stage-d/{'dry-run' if dry else 'submit-edits'}"
            form = aiohttp.FormData()
            form.add_field("file", data, filename=doc.file_name,
                           content_type="application/x-yaml" if name.endswith(('.yaml', '.yml')) else "application/json")
            form.add_field("title", title)
            if dry: form.add_field("kind", "edits")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180, connect=10, sock_read=120)) as sess:
                async with sess.post(url, data=form, headers=headers) as resp:
                    if resp.status < 300:
                        j = await resp.json()
                        files = j.get("files", [])
                        await message.reply(f"✅ Spec {'(dry-run) ' if dry else ''}ok\nBranch: {j.get('branch')}\nFiles: {', '.join(files) if files else '(none)'}")
                    else:
                        await message.reply(f"❌ Spec error {resp.status}.")
        except Exception as e:
            await message.reply(f"❌ Spec failed: {e}")
