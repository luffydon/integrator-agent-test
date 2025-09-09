# app/integrations/telegram.py
import os, httpx
from typing import Optional, Dict, Any

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

class TelegramClient:
    def __init__(self):
        if not API:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
        self.api = API

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: Optional[bool] = None,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ):
        """
        Attempts to send a message to Telegram and prints the outcome to the terminal.
        """
        print("--- Outgoing Telegram Message ---")
        print(f"Chat ID: {chat_id}")
        print(f"Message: {text}")
        print("--------------------------------")

        payload = {"chat_id": chat_id, "text": text}
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        # --- Start Correction ---
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            payload["disable_web_page_preview"] = disable_web_page_preview
        # --- End Correction ---

        try:
            async with httpx.AsyncClient(timeout=10) as cx:
                r = await cx.post(f"{self.api}/sendMessage", json=payload)
                r.raise_for_status()
            print("✅ Message successfully sent to Telegram.")
            return r.json()
        except httpx.ConnectError as e:
            print(f"❌ CONNECTION ERROR: The message was not sent. Error: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred while sending message: {e}")

    async def answer_callback_query(self, callback_query_id: str):
        """Answers a callback query to remove the 'loading' state from the button."""
        payload = {"callback_query_id": callback_query_id}
        try:
            async with httpx.AsyncClient(timeout=5) as cx:
                r = await cx.post(f"{self.api}/answerCallbackQuery", json=payload)
                r.raise_for_status()
        except Exception as e:
            print(f"❌ Failed to answer callback query: {e}")