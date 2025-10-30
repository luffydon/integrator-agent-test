# Telegram webhook patch (no aiogram)

Adds exactly what you requested **on top of your repo**:
- /revert — triggers Stage C workflow to previous GitHub release.
- Add service from file — accepts JSON/NDJSON, supports multiple services, **no “service name?” prompt**.
- Keeps Stage A (.zip) and /promote.

Files:
- app/utils/telegram_client.py
- app/tg/webhook.py

Wire in FastAPI:
    from app.tg.webhook import router as tg_webhook_router
    app.include_router(tg_webhook_router)

Set webhook:
    curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" -H "Content-Type: application/json" -d '{"url":"https://YOUR_HOST/tg/SECRET/update"}'

Env:
- BOT_TOKEN (or TELEGRAM_BOT_TOKEN)
- TG_WEBHOOK_SECRET
- INTEGRATOR_BASE_URL
- PROMOTE_ADMIN_TOKEN (if your integrator needs it)
- For /revert: GITHUB_OWNER, GITHUB_REPO, INTEGRATOR_GITHUB_TOKEN or GITHUB_TOKEN (workflows scope)
