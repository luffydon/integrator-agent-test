# Stage A stopped after /revert? Quick fix

This patch makes the Telegram → Integrator Stage A call **robust** across env changes.

## What changed
- Resolves INTEGRATOR_BASE_URL from multiple env names: `INTEGRATOR_BASE_URL`, `INTEGRATOR_URL`, `INTEGRATOR_API` (fallback `http://localhost:8000`).
- Sends **multiple auth headers** if you set `PROMOTE_ADMIN_TOKEN` (or `INTEGRATOR_ADMIN_TOKEN`): `X-Integrator-Admin`, `X-Promote-Admin`, and `Authorization: Bearer <token>`—covers older/newer integrator builds.
- Accepts slightly larger zips (default 80MB) and returns **clear error messages** (401/403/404).
- Adds `GET /tg/diag` to see current integrator URL and whether a token is attached.

## How to use
1. Stage A upload this patch zip, then /promote.
2. Hit `GET /tg/diag` on your API host (no auth) to confirm:
   - `integrator_base_url` points to the correct integrator
   - `has_admin_token` is `true` if your integrator requires it
3. Try sending a `.zip` again—should reply with `✅ Stage A uploaded`.

## If it still fails
- Set env on the bot app:
  - `INTEGRATOR_BASE_URL=https://<your-integrator-host>`
  - (if needed) `PROMOTE_ADMIN_TOKEN=<secret>`
- Redeploy (or just upload another patch + promote).