from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query

from app.security import require_router_secret as _require_secret 

from app.agent_models import (
    Agent, AgentCreateRequest, AgentUpdateRequest,
    TeachRequest, ToolExecRequest, MemoryRecord
)
from app.core import agent_manager as mgr

router = APIRouter(prefix="/router", tags=["agents"])

@router.get("/agents", response_model=list[Agent], dependencies=[Depends(_require_secret)])
def list_agents(include_archived: int = Query(0, ge=0, le=1)):
    return mgr.list_agents(include_archived=bool(include_archived))

@router.post("/agents", response_model=Agent, dependencies=[Depends(_require_secret)], status_code=201)
def create_agent(req: AgentCreateRequest):
    try:
        return mgr.create_agent(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/agents/{agent_id}", response_model=Agent, dependencies=[Depends(_require_secret)])
def get_agent(agent_id: str):
    ag = mgr.get_agent(agent_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Not found")
    return ag

@router.patch("/agents/{agent_id}", response_model=Agent, dependencies=[Depends(_require_secret)])
def update_agent(agent_id: str, req: AgentUpdateRequest):
    ag = mgr.update_agent(agent_id, req)
    if not ag:
        raise HTTPException(status_code=404, detail="Not found")
    return ag

@router.delete("/agents/{agent_id}", dependencies=[Depends(_require_secret)])
def delete_agent(agent_id: str):
    ok = mgr.archive_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "archived": True}

# Brains / Teach
@router.post("/agents/{agent_id}/teach", response_model=MemoryRecord, dependencies=[Depends(_require_secret)])
def teach(agent_id: str, req: TeachRequest):
    try:
        return mgr.teach(agent_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/agents/{agent_id}/brain", response_model=list[MemoryRecord], dependencies=[Depends(_require_secret)])
def brain(agent_id: str, scope: Optional[str] = None, user_id: Optional[str] = None, tag: Optional[str] = None, limit: int = 100):
    return mgr.read_brain(agent_id, scope=scope, user_id=user_id, tag=tag, limit=limit)

# Tools registry view + assign + exec
@router.get("/tools", dependencies=[Depends(_require_secret)])
def list_tools() -> Dict[str, Any]:
    try:
        from app.tools import registry as tools_registry  # type: ignore
    except Exception:
        return {"ok": True, "tools": {}}
    reg = getattr(tools_registry, "REGISTRY", None)
    if reg is None:
        get_reg = getattr(tools_registry, "get_registry", None)
        reg = get_reg() if callable(get_reg) else {}
    out: Dict[str, Any] = {}
    if isinstance(reg, dict):
        for k, v in reg.items():
            title = getattr(v, "title", k)
            desc = getattr(v, "description", "")
            out[k] = {"title": title, "description": desc}
    else:
        try:
            for v in reg:
                k = getattr(v, "key", None)
                if not k:
                    continue
                out[k] = {"title": getattr(v, "title", k), "description": getattr(v, "description", "")}
        except Exception:
            out = {}
    return {"ok": True, "tools": out}

@router.put("/agents/{agent_id}/tools", dependencies=[Depends(_require_secret)])
def set_agent_tools(agent_id: str, tools: list[str]):
    ag = mgr.update_agent(agent_id, AgentUpdateRequest(tools_allowed=tools))
    if not ag:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "agent": ag}

@router.post("/agents/{agent_id}/tools/exec", dependencies=[Depends(_require_secret)])
def tools_exec(agent_id: str, req: ToolExecRequest):
    return mgr.exec_tool(agent_id, req.tool, req.params, req.context or {})
