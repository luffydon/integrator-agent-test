# app/utils/telegram_client.py
import os
import aiohttp

BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

class TG:
    def __init__(self, token: str | None = None):
        self.token = token or BOT_TOKEN
        if not self.token:
            raise RuntimeError("BOT_TOKEN env var is required for Telegram API.")
        self.base = f"https://api.telegram.org/bot{self.token}"
        self.file_base = f"https://api.telegram.org/file/bot{self.token}"

    async def send_message(self, chat_id: int | str, text: str):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=10, sock_read=40)) as s:
            # Don't raise here; webhook should still return 200
            await s.post(f"{self.base}/sendMessage", json={"chat_id": chat_id, "text": text})

    async def get_file_meta(self, file_id: str) -> dict:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=10, sock_read=40)) as s:
            r = await s.get(f"{self.base}/getFile", params={"file_id": file_id})
            if r.status >= 300:
                raise RuntimeError(f"TG getFile failed {r.status}: {await r.text()}")
            return await r.json()

    async def download_file_by_path(self, file_path: str) -> bytes:
        url = f"{self.file_base}/{file_path}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300, connect=10, sock_read=240)) as s:
            r = await s.get(url)
            if r.status >= 300:
                raise RuntimeError(f"TG file download failed {r.status}: {await r.text()}")
            return await r.read()
