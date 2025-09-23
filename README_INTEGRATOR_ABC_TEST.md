# Integrator ABC Test Payload

This bundle is designed to exercise **Stage A → B → C**:

- **A:** upload this zip via Telegram bot → creates a branch `stage-a/<slug>`
- **B:** `/promote stage-a/<slug>` → PR auto-merge + tag
    - DB step **will** run (new migration present)
    - Fly deploy **will** run (app/ change present)
- **C:** Release + health check

## What’s inside
- `app/__deploy_probe__.txt` — harmless file to trigger application deploy logic
- `db/migrations/2025-09-23__integrator_probe.sql` — Postgres-safe IF NOT EXISTS table
- `README_INTEGRATOR_ABC_TEST.md` — this file

## Use
1. Send this zip to your Telegram bot **as a file**.
2. Copy the returned branch name (e.g., `stage-a/tg-...`).
3. Run: `/promote stage-a/<branch>` in the bot.
4. Watch GitHub Actions: Stage B (db + fly) then Stage C (release/verify).

## Notes
- The SQL migration creates a table `integrator_probe`.
- The `app/__deploy_probe__.txt` just forces a rebuild/deploy; it is not used at runtime.
- Remove these artifacts later via a follow-up change if desired.

Generated: 2025-09-23 05:31:28
