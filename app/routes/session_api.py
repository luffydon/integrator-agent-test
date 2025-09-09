# app/routes/session_api.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.core import session_store as sess
from app.core import agent_manager as mgr
from app.security import require_router_secret as _require_secret  # <-- add this

router = APIRouter(prefix="/session", tags=["session"])

@router.post("/agent/select", dependencies=[Depends(_require_secret)])
def select_agent(chat_id: str, agent_id: str):
    if not mgr.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    sess.set_active(chat_id, agent_id)
    return {"ok": True, "chat_id": chat_id, "active_agent_id": agent_id}

@router.get("/agent", dependencies=[Depends(_require_secret)])
def get_selected_agent(chat_id: str = Query(...)):
    return {"chat_id": chat_id, "active_agent_id": sess.get_active(chat_id)}
