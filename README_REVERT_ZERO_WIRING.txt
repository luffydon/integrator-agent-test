# Revert by Branch — Zero‑wiring patch

This patch adds a single GitHub Actions workflow that opens a **revert PR** for any previously **promoted Stage‑A branch**.

Why this is 100% wiring‑free:
- No Python files changed.
- No Telegram code to wire.
- No env renames; uses the built‑in `${{ secrets.GITHUB_TOKEN }}`.

How to use:
1. Go to **GitHub → Actions → Revert by Branch → Run workflow**.
2. Enter the Stage‑A branch, e.g. `stage-a/20251103-wave-house`.
3. The workflow finds the merged PR, creates `revert/<slug>/<runid>`, runs a merge‑aware `git revert`, pushes, and opens a PR.

Safe with Stage‑A: add‑only, no imports affected.
