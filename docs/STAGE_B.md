# Stage B — Promotion to Production

## API
POST /integrations/stage-b/promote
Headers (required if PROMOTE_ADMIN_TOKEN is set):
  X-Integrator-Admin: <token>
Body:
  { "branch": "stage-a/YYYYMMDD-slug" }

## Env (Integrator runtime)
- GITHUB_TOKEN  (contents + PRs read/write)
- GITHUB_REPO   (owner/repo)
- GITHUB_BASE   (e.g., main)
- PROMOTE_ADMIN_TOKEN  (optional, for simple header-based auth)

## GitHub Actions Secrets
- DATABASE_URL_PROD
- FLY_API_TOKEN_PROD
- PROD_HEALTH_URL

## Flow
- Ensures branch exists
- Creates/reuses PR to base, merges (squash)
- Tags merge commit: release/<branch-with-slashes-replaced>
- stage-b.yml runs: backup → migrate → deploy → health → rollback on failure
