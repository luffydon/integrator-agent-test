# bot/tg_stage_a.py
import os, time, aiohttp
from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext

INTEGRATOR_BASE_URL = os.environ.get("INTEGRATOR_BASE_URL", "http://localhost:8000")
ADMIN_HEADER_NAME   = "X-Integrator-Admin"
ADMIN_HEADER_VALUE  = os.environ.get("PROMOTE_ADMIN_TOKEN", "")
MAX_ZIP_BYTES       = int(os.environ.get("STAGE_A_MAX_ZIP_BYTES", str(60 * 1024 * 1024)))  # 60MB

_WIRED = False

def wire_stage_a(dp: Dispatcher, bot_token: str):
    global _WIRED
    if _WIRED:
        return
    _WIRED = True

    @dp.message_handler(content_types=["document"], state="*")
    async def handle_zip(message: types.Message, state: FSMContext):
        if await state.get_state():
            await state.finish()

        doc = message.document
        if not doc or not (doc.file_name or "").lower().endswith(".zip"):
            return

        if doc.file_size and doc.file_size > MAX_ZIP_BYTES:
            await message.reply("❌ ZIP is too large. Please keep it under 60MB.")
            return

        try:
            file = await dp.bot.get_file(doc.file_id)
            tg_url = f"https://api.telegram.org/file/bot{bot_token}/{file.file_path}"
            timeout = aiohttp.ClientTimeout(total=180, connect=10, sock_read=120)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.get(tg_url) as r:
                    r.raise_for_status()
                    zip_bytes = await r.read()
        except Exception as e:
            await message.reply(f"❌ Failed to download ZIP: {e}")
            return

        if len(zip_bytes) > MAX_ZIP_BYTES:
            await message.reply("❌ ZIP is too large after download. Please keep it under 60MB.")
            return

        try:
            timeout = aiohttp.ClientTimeout(total=300, connect=10, sock_read=240)
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                form = aiohttp.FormData()
                form.add_field("file", zip_bytes, filename=doc.file_name, content_type="application/zip")
                form.add_field("title", f"tg-{message.from_user.username or 'user'}-{int(time.time())}")
                headers = {ADMIN_HEADER_NAME: ADMIN_HEADER_VALUE} if ADMIN_HEADER_VALUE else {}
                async with sess.post(f"{INTEGRATOR_BASE_URL}/integrations/stage-a/submit-zip",
                                     data=form, headers=headers) as resp:
                    if resp.status < 300:
                        j = await resp.json()
                        await message.reply(f"✅ Uploaded\nBranch: {j.get('branch','(unknown)')}")
                    else:
                        txt = await resp.text()
                        await message.reply(f"❌ Stage A error {resp.status}\n{txt[:400]}")
        except Exception as e:
            await message.reply(f"❌ Stage A failed: {e}")
