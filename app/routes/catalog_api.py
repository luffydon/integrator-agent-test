from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Query

from app.core import agent_manager as mgr
from app.agent_models import Agent

router = APIRouter(prefix="/catalog", tags=["catalog"])

@router.get("/agents")
def public_agents(q: Optional[str] = Query(None), lang: Optional[str] = Query(None), limit: int = 50):
    agents: List[Agent] = mgr.list_agents(include_archived=False)
    out = []
    for a in agents:
        if a.visibility not in ("public", "unlisted"):
            continue
        if q and q.lower() not in a.name.lower():
            continue
        out.append({
            "id": a.id,
            "name": a.name,
            "emoji": a.emoji,
            "blurb": a.description,
            "languages": [],
            "visibility": a.visibility,
        })
        if len(out) >= max(1, min(limit, 200)):
            break
    return out
