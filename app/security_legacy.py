# app/security.py
import os
from typing import Optional
from fastapi import Header, HTTPException

def require_router_secret(
    # Let FastAPI map "X-Router-Secret" -> x_router_secret
    x_router_secret: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    # Let FastAPI map "X-API-Key" -> x_api_key
    x_api_key: Optional[str] = Header(None),
) -> None:
    admin  = os.getenv("APP_SECRET_KEY")
    llm    = os.getenv("APP_LLM_SECRET")   
    legacy = os.getenv("ROUTER_SECRET")    

    allowed = [t for t in (admin, llm, legacy) if t]
    if not allowed:   # no secret configured -> allow in dev
        return

    presented = []
    if x_router_secret:
        presented.append(x_router_secret)
    if x_api_key:
        presented.append(x_api_key)
    if authorization and authorization.lower().startswith("bearer "):
        presented.append(authorization.split(" ", 1)[1].strip())

    if any(p in allowed for p in presented):
        return

    raise HTTPException(status_code=401, detail="Unauthorized")
