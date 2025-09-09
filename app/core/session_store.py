from __future__ import annotations
import os, json, threading
from pathlib import Path
from typing import Optional, Dict, Any

_DATA_DIR = Path(os.getenv("ROUTER_DATA_DIR", "/mnt/data/router_data")).resolve()
_SESS_PATH = _DATA_DIR / "chat_sessions.json"
_LOCK = threading.Lock()

def _load() -> dict:
    if not _SESS_PATH.exists():
        return {}
    try:
        with _SESS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(d: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _SESS_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    tmp.replace(_SESS_PATH)

def get_session(chat_id: str) -> Dict[str, Any]:
    """Gets the full session data for a chat."""
    with _LOCK:
        d = _load()
        return d.get(chat_id, {})

def update_session(chat_id: str, data: Dict[str, Any]) -> None:
    """Updates the session data for a chat."""
    with _LOCK:
        d = _load()
        if chat_id not in d:
            d[chat_id] = {}
        # Merge the new data into the existing session
        d[chat_id].update(data)
        _save(d)

def clear_session_state(chat_id: str) -> None:
    """Clears the conversational state, but keeps the active agent."""
    with _LOCK:
        d = _load()
        if chat_id in d:
            # Preserve active_agent if it exists
            active_agent = d[chat_id].get("active_agent")
            d[chat_id] = {}
            if active_agent:
                d[chat_id]["active_agent"] = active_agent
            _save(d)

def set_active(chat_id: str, agent_id: str) -> None:
    """Sets the active agent for a chat."""
    update_session(chat_id, {"active_agent": agent_id})

def get_active(chat_id: str) -> Optional[str]:
    """Gets the active agent for a chat."""
    return get_session(chat_id).get("active_agent")

def clear_active(chat_id: str) -> None:
    """Clears the active agent for a chat."""
    with _LOCK:
        d = _load()
        if chat_id in d and "active_agent" in d[chat_id]:
            del d[chat_id]["active_agent"]
            _save(d)