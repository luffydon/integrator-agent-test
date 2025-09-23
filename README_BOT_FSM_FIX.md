# Bot FSM Fix Bundle (ZIP/JSON always handled, cancel escape, no prompts)

This bundle makes your bot react to every upload (even after a previous flow),
adds universal /cancel/quit escape, and stops asking for a service name when you
send JSON (file or text). It keeps your existing CI (promote triggers deploy).

## Files
- bot/escapes.py
- bot/tg_stage_a.py
- bot/tg_stage_d.py
- bot/service_json_text.py

## Wire (order matters)
```python
from bot.escapes import wire_escapes
from bot.tg_stage_a import wire_stage_a
from bot.tg_stage_d import wire_stage_d
from bot.service_json_text import wire_service_json_text

wire_escapes(dp)                # 1) cancel/quit first
wire_stage_a(dp, BOT_TOKEN)     # 2) ZIP uploads always work
wire_stage_d(dp, BOT_TOKEN)     # 3) patch/spec + JSON file flow
wire_service_json_text(dp, BOT_TOKEN)  # 4) pasted JSON, no prompts
```

## Env expected
- BOT_TOKEN
- INTEGRATOR_BASE_URL
- optional: PROMOTE_ADMIN_TOKEN
- optional: STAGE_A_MAX_ZIP_BYTES, MAX_EDIT_UPLOAD_BYTES, MAX_SERVICE_JSON_BYTES

Generated: 2025-09-23 07:17:20
