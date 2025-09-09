from __future__ import annotations

import uuid, hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Iterable

from pydantic import ValidationError
from sqlalchemy import select
from app.db import SessionLocal
from app.agent_models import (
    Agent, AgentCreateRequest, AgentUpdateRequest,
    TeachRequest, MemoryRecord
)
from app.models_agents import AgentDB, AgentMemoryDB

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _tz(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _to_agent_schema(row: AgentDB) -> Agent:
    return Agent(
        id=row.id,
        name=row.name,
        description=row.description,
        emoji=row.emoji,
        visibility=row.visibility,
        teachable=row.teachable,
        tools_allowed=row.tools_allowed or [],
        status=row.status,
        created_at=_tz(row.created_at) or _utcnow(),
        updated_at=_tz(row.updated_at) or _tz(row.created_at) or _utcnow(),
    )

def _to_memory_schema(m: AgentMemoryDB) -> MemoryRecord:
    return MemoryRecord(
        memory_id=m.memory_id,
        scope=m.scope,
        user_id=m.user_id,
        tags=m.tags or [],
        content=m.content,
        created_at=_tz(m.created_at) or _utcnow(),
    )

def _validate_tools(tools: Optional[List[str]]) -> List[str]:
    if not tools:
        return []
    available = set()
    try:
        from app.tools import registry as tools_registry  # type: ignore
        reg = getattr(tools_registry, "REGISTRY", None)
        if reg is None:
            get_reg = getattr(tools_registry, "get_registry", None)
            reg = get_reg() if callable(get_reg) else {}
        if isinstance(reg, dict):
            available = set(reg.keys())
        elif isinstance(reg, Iterable):
            available = set([getattr(x, "key", None) for x in reg if getattr(x, "key", None)])
    except Exception:
        available = set()
    return [t for t in tools if t in available] if available else list(tools)

def list_agents(include_archived: bool = False) -> List[Agent]:
    with SessionLocal() as db:
        rows = db.scalars(select(AgentDB)).all()
        out: List[Agent] = []
        for r in rows:
            if not include_archived and r.status == "archived":
                continue
            try:
                out.append(_to_agent_schema(r))
            except ValidationError:
                continue
        return out

def get_agent(agent_id: str) -> Optional[Agent]:
    with SessionLocal() as db:
        row = db.get(AgentDB, agent_id)
        return _to_agent_schema(row) if row else None

def create_agent(req: AgentCreateRequest) -> Agent:
    with SessionLocal() as db:
        existing = db.execute(select(AgentDB).where(AgentDB.name == req.name)).scalar_one_or_none()
        if existing and existing.status != "archived":
            raise ValueError("Agent with this name already exists")
        now = _utcnow()
        row = AgentDB(
            id=f"agent_{uuid.uuid4().hex[:8]}",
            name=req.name,
            description=req.description,
            emoji=req.emoji,
            visibility=req.visibility,
            teachable=req.teachable,
            tools_allowed=_validate_tools(req.tools_allowed),
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_agent_schema(row)

def update_agent(agent_id: str, req: AgentUpdateRequest) -> Optional[Agent]:
    with SessionLocal() as db:
        row = db.get(AgentDB, agent_id)
        if not row:
            return None
        for field in ["name", "description", "emoji", "visibility", "teachable", "status"]:
            val = getattr(req, field, None)
            if val is not None:
                setattr(row, field, val)
        if req.tools_allowed is not None:
            row.tools_allowed = _validate_tools(req.tools_allowed)
        row.updated_at = _utcnow()
        db.commit()
        db.refresh(row)
        try:
            return _to_agent_schema(row)
        except ValidationError:
            return None

def archive_agent(agent_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(AgentDB, agent_id)
        if not row:
            return False
        row.status = "archived"
        row.updated_at = _utcnow()
        db.commit()
        return True

def teach(agent_id: str, req: TeachRequest) -> MemoryRecord:
    with SessionLocal() as db:
        ag = db.get(AgentDB, agent_id)
        if not ag:
            raise ValueError("Agent not found")
        
        # This line is changed to include a timestamp, ensuring a unique ID
        now = _utcnow()
        hash_input = f"{req.content}-{req.user_id or ''}-{now.isoformat()}"
        memory_id = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()[:12]

        mem = AgentMemoryDB(
            memory_id=memory_id,
            agent_id=agent_id,
            scope=req.scope,
            user_id=req.user_id,
            tags=req.tags or [],
            content=req.content,
            created_at=now,
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return _to_memory_schema(mem)

def read_brain(agent_id: str, scope: Optional[str] = None, user_id: Optional[str] = None,
               tag: Optional[str] = None, limit: int = 100):
    with SessionLocal() as db:
        q = select(AgentMemoryDB).where(AgentMemoryDB.agent_id == agent_id)
        if scope in ("shared", "per_user"):
            q = q.where(AgentMemoryDB.scope == scope)
        rows = db.scalars(q).all()
        out = []
        for m in rows:
            if user_id and m.user_id != user_id:
                continue
            if tag and tag not in (m.tags or []):
                continue
            out.append(_to_memory_schema(m))
            if len(out) >= max(1, min(limit, 500)):
                break
        return out

def exec_tool(agent_id: str, tool_key: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ag = get_agent(agent_id)
    if not ag:
        return {"ok": False, "error": "agent_not_found"}
    if tool_key not in (ag.tools_allowed or []):
        return {"ok": False, "error": "tool_not_allowed"}
    try:
        from app.tools import runner as tools_runner  # type: ignore
        if hasattr(tools_runner, "exec_tool"):
            return tools_runner.exec_tool(agent_id=agent_id, key=tool_key, params=params, ctx=context or {})
        if hasattr(tools_runner, "run"):
            out = tools_runner.run(tool_key, params, context or {})
            return {"ok": True, "output": out}
        return {"ok": False, "error": "runner_missing_exec_tool"}
    except Exception as e:
        return {"ok": False, "error": f"runner_error: {e}"}

def log_message(agent_id: str, content: str, user_id: Optional[str] = None, tag: str = "msg") -> MemoryRecord:
    return teach(agent_id, TeachRequest(content=content, scope="shared", user_id=user_id, tags=[tag]))
