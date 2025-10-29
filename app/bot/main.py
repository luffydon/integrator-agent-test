# app/bot/main.py (patched to wire direct add from JSON)
import os
from aiogram import Bot, Dispatcher
from aiogram.utils import executor

from app.bot.tg_add_service_direct import wire_add_service_direct

# If your original main.py includes more wiring (stage_a, stage_b, etc.),
# keep it; this minimal file ensures the new handler is active.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Register the direct add handler early (before other parsers/wizards).
wire_add_service_direct(dp)

async def on_startup(_): pass

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
