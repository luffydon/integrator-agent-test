# Revert — Roll back last deploy (add-only)

This patch adds a **safe revert workflow** that rolls back your Fly app to the **previous image**.
It does **not** change any runtime code and **will not** break Stage A or your bot.

## Files
- `.github/workflows/revert.yml` — GitHub Actions workflow (manual Run)
- `docs/REVERT.md` — this guide

## Prereqs
- GitHub secrets set (already used by your Stage B/C):
  - `FLY_API_TOKEN_PROD`
  - `PROD_HEALTH_URL` (optional; for health checks)
- GitHub variable:
  - `FLY_APP` (or `fly.prod.toml` present in repo)

## Usage
1. Go to **Actions → Revert — Roll back last deploy → Run workflow**.
2. Keep `deploy_prod` = true (default).
3. Watch the job. It will:
   - fetch Fly releases,
   - pick the **previous** image (`releases[1].image_ref`),
   - `flyctl deploy --image <that-image>`,
   - (optional) health check via `PROD_HEALTH_URL`.
4. Your service returns to the prior deploy.

This is **add-only** and cannot conflict with your current code.
