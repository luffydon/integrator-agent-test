# Service JSON Text Handler (no prompts)

This adds a handler that recognizes **text messages** containing JSON like:

```
add service:{ "business_name": "Wave House", "title": "Surfboard Rental", ... }
```

It parses the JSON, derives a **service slug** automatically, and replies **without asking** for a name.
No Integrator/CI calls are made here — this only fixes the *prompting* behavior.

## Files
- `bot/service_json_text.py` — the handler

## Wire it
In your bot startup (e.g., `bot/main.py`), import and call:

```python
from bot.service_json_text import wire_service_json_text
wire_service_json_text(dp, BOT_TOKEN)
```

Place this **before** any legacy handlers that ask for a service name.

## Env (optional)
- `MAX_SERVICE_JSON_BYTES` (default `512000`)

## How it derives the slug
Order: `name` → `service.name` → `metadata.name` → `id` → `title` → `business_name` → fallback.
Slug chars: `[a-z0-9._-]`, max 60 chars.

Generated: 2025-09-23 06:25:49
