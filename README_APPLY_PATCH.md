# Patch: Add Services from JSON (wired automatically)

This patch wires the handler automatically. After deployment:

Send in Telegram:
```
add services:[
  {"title":"Surfboard Rental","currency":"VND","base_price":150000,"location":"My Khe Beach"},
  {"title":"Beach Yoga Class","currency":"VND","base_price":120000,"location":"My An"}
]
```
The bot should reply `Created 2/2 services: …`.

Files:
- app/bot/tg_add_service_direct.py
- app/bot/main.py (minimal boot that wires the handler)

If you have a richer main.py, re-merge the `from app.bot.tg_add_service_direct import wire_add_service_direct`
and `wire_add_service_direct(dp)` into it after testing.
