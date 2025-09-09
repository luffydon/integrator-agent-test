# app/admin_guard.py
import os
from fastapi import Header, HTTPException

def _mask(tok: str | None) -> str:
    if not tok:
        return ""
    if len(tok) <= 4:
        return "*" * len(tok)
    return tok[:2] + "*" * (len(tok)-4) + tok[-2:]

def require_admin(authorization: str | None = Header(default=None)):
    """STRICT admin: ONLY Authorization: Bearer <ADMIN_TOKEN>"""
    admin = os.getenv("ADMIN_TOKEN", "").strip()
    if not admin:
        print("[require_admin] ADMIN_TOKEN not configured")
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured")

    if not authorization or not authorization.lower().startswith("bearer "):
        print(f"[require_admin] missing/invalid Authorization; expected Bearer {_mask(admin)}")
        raise HTTPException(status_code=403, detail="Admins only (Bearer required)")

    token = authorization.split(" ", 1)[1].strip()
    if token != admin:
        print(f"[require_admin] token mismatch; got {_mask(token)} expected {_mask(admin)}")
        raise HTTPException(status_code=403, detail="Admins only (invalid token)")
