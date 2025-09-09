import os
from fastapi import Header, HTTPException

def require_router_secret(x_router_secret: str | None = Header(default=None)):
    """
    INTERNAL trust only (webhooks / service-to-service). NOT admin.
    """
    app_secret = os.getenv("APP_SECRET_KEY", "").strip()
    if not app_secret:
        raise HTTPException(status_code=500, detail="APP_SECRET_KEY not configured")
    if x_router_secret != app_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True

# re-export strict admin
from .auth import require_admin
