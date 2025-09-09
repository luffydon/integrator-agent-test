from fastapi import APIRouter, Depends, Body, HTTPException
from app.security.auth import require_admin
from app.db import SessionLocal

# -----------------------------
# Try Session store (class or functions)
# -----------------------------
_SSESSION_DEBUG = []

SessionStore = None  # type: ignore
_get_active_agent = None
_set_active_agent = None

try:
    # Preferred: class-based API
    from app.core.session_store import SessionStore as _SessionStore  # type: ignore
    SessionStore = _SessionStore
    _SSESSION_DEBUG.append("Imported class SessionStore from app.core.session_store")
except Exception as e1:
    _SSESSION_DEBUG.append(f"Class SessionStore not found: {e1}")
    try:
        # Fallback: function-based API
        from app.core.session_store import (  # type: ignore
            get_active_agent as _get_active_agent,
            set_active_agent as _set_active_agent,
        )
        _SSESSION_DEBUG.append("Imported functions get_active_agent/set_active_agent from app.core.session_store")
        class _ShimSessionStore:  # type: ignore
            def get_active_agent(self, db, chat_id: str):
                return _get_active_agent(db, chat_id)
            def set_active_agent(self, db, chat_id: str, agent_id: str):
                return _set_active_agent(db, chat_id, agent_id)
        SessionStore = _ShimSessionStore
    except Exception as e2:
        _SSESSION_DEBUG.append(f"Functions get_active_agent/set_active_agent not found: {e2}")

if SessionStore is None:
    # Last-resort shim – in-memory (dev only) to avoid hard crash
    _SSESSION_DEBUG.append("Using DEV in-memory SessionStore shim (no persistence)")
    class _DevSessionStore:  # type: ignore
        _mem = {}
        def get_active_agent(self, db, chat_id: str):
            return self._mem.get(chat_id)
        def set_active_agent(self, db, chat_id: str, agent_id: str):
            self._mem[chat_id] = agent_id
    SessionStore = _DevSessionStore  # type: ignore

# -----------------------------
# Try Agent manager
# -----------------------------
_agent_debug = []

try:
    from app.core.agent_manager import AgentManager  # type: ignore
    _agent_debug.append("Imported AgentManager from app.core.agent_manager")
except Exception as e:
    _agent_debug.append(f"AgentManager not found: {e}; using DB fallback")
    # Generic DB fallback using your SQLAlchemy Agent model
    from typing import Any, Dict, List, Optional
    from sqlalchemy.orm import Session
    from app import models_agents as ma  # expects ma.Agent model

    class AgentManager:  # type: ignore
        def _row_to_dict(self, row: Any) -> Dict[str, Any]:
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

        def list_agents(self, db: Session) -> List[Dict[str, Any]]:
            q = db.query(ma.Agent)
            if hasattr(ma.Agent, "is_archived"):
                q = q.filter(ma.Agent.is_archived == False)  # noqa: E712
            return [self._row_to_dict(r) for r in q.all()]

        def get_agent(self, db: Session, agent_id: str) -> Optional[Dict[str, Any]]:
            r = db.query(ma.Agent).filter(ma.Agent.id == agent_id).first()
            return self._row_to_dict(r) if r else None

        def create_agent(self, db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
            r = ma.Agent(**data)
            db.add(r); db.commit(); db.refresh(r)
            return self._row_to_dict(r)

        def update_agent(self, db: Session, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            r = db.query(ma.Agent).filter(ma.Agent.id == agent_id).first()
            if not r: return None
            for k, v in data.items():
                if hasattr(r, k):
                    setattr(r, k, v)
            db.commit(); db.refresh(r)
            return self._row_to_dict(r)

        def archive_agent(self, db: Session, agent_id: str) -> bool:
            r = db.query(ma.Agent).filter(ma.Agent.id == agent_id).first()
            if not r: return False
            if hasattr(r, "is_archived"):
                setattr(r, "is_archived", True); db.commit(); return True
            db.delete(r); db.commit(); return True

# -----------------------------
# Runtime wrapper (your orchestrator)
# -----------------------------
from app.services.router_service import handle_agent_message

router = APIRouter()

agents = AgentManager()
sessions = SessionStore()  # type: ignore


# DB dependency
def db_dep():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------
# Health (also prints debug)
# --------------------------
@router.get("/health")
def health():
    return {
        "ok": True,
        "source": "http_api",
        "session_import": _SSESSION_DEBUG,
        "agent_import": _agent_debug,
    }


# --------------------------
# Agents (CRUD)
# --------------------------
@router.get("/router/agents")
def api_list_agents(db=Depends(db_dep)):
    out = agents.list_agents(db)
    print(f"🧭 [agents.list] {len(out)} item(s)")
    return {"agents": out}

@router.get("/router/agents/{agent_id}")
def api_get_agent(agent_id: str, db=Depends(db_dep)):
    out = agents.get_agent(db, agent_id)
    if not out:
        raise HTTPException(status_code=404, detail="Agent not found")
    print(f"🧭 [agents.get] {agent_id}")
    return {"agent": out}

@router.post("/router/agents", dependencies=[Depends(require_admin)])
def api_create_agent(payload: dict = Body(...), db=Depends(db_dep)):
    out = agents.create_agent(db, payload)
    print(f"🧭 [agents.create] {out.get('id')}")
    return {"agent": out}

@router.put("/router/agents/{agent_id}", dependencies=[Depends(require_admin)])
def api_update_agent(agent_id: str, payload: dict = Body(...), db=Depends(db_dep)):
    out = agents.update_agent(db, agent_id, payload)
    if not out:
        raise HTTPException(status_code=404, detail="Agent not found")
    print(f"🧭 [agents.update] {agent_id}")
    return {"agent": out}

@router.delete("/router/agents/{agent_id}", dependencies=[Depends(require_admin)])
def api_archive_agent(agent_id: str, db=Depends(db_dep)):
    ok = agents.archive_agent(db, agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    print(f"🧭 [agents.archive] {agent_id}")
    return {"ok": True}


# --------------------------
# Session active agent
# --------------------------
@router.get("/router/session/agent")
def api_get_session_agent(chat_id: str, db=Depends(db_dep)):
    aid = sessions.get_active_agent(db, chat_id)
    print(f"🧭 [session.get] chat={chat_id} -> agent={aid}")
    return {"agent_id": aid}

@router.post("/router/session/agent")
def api_set_session_agent(chat_id: str, agent_id: str, db=Depends(db_dep)):
    sessions.set_active_agent(db, chat_id, agent_id)
    print(f"🧭 [session.set] chat={chat_id} -> agent={agent_id}")
    return {"ok": True}


# --------------------------
# Runtime entrypoint
# --------------------------
@router.post("/router/agent/message")
def api_handle_agent_message(payload: dict = Body(...), db=Depends(db_dep)):
    chat_id = str(payload.get("chat_id", "")).strip()
    user_id = str(payload.get("user_id", "")).strip()
    text = (payload.get("text") or "").strip()
    agent_id = payload.get("agent_id")

    if not chat_id or not user_id or not text:
        raise HTTPException(status_code=400, detail="chat_id, user_id and text are required")

    print(f"🧭 [message] chat={chat_id} user={user_id} agent={agent_id} text='{text[:60]}'")
    return handle_agent_message(chat_id=chat_id, user_id=user_id, text=text, agent_id=agent_id)
