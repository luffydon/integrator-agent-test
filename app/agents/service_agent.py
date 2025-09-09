from __future__ import annotations
import os, json, inspect, logging
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path

from app.llm import LLMClient
from app.clients import backend_api as be

logger = logging.getLogger(__name__)
USE_INTENT_ENGINE = os.getenv("USE_INTENT_ENGINE", "true").lower() == "true"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "orchestrator_prompt.txt"

try: SYS_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
except Exception: SYS_PROMPT = "You are the orchestrator agent. Use tools when helpful and keep answers short."

CHAT_HISTORY: Dict[str, List[Dict[str, Any]]] = {}

TOOLS = [
    {"type": "function", "function": {"name": "browse_services", "description": "Search or list public services for the user.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": [],},},},
    {"type": "function", "function": {"name": "list_categories", "description": "Return available service categories.", "parameters": {"type": "object", "properties": {}, "required": []},},},
    # --- START CORRECTION ---
    {"type": "function", "function": {"name": "create_service", "description": "Creates a new service for a business.", "parameters": {
        "type": "object",
        "properties": {
            "business_name": {"type": "string", "description": "The name of the business offering the service."},
            "name": {"type": "string", "description": "The name of the new service."},
            "description": {"type": "string", "description": "A description of the service."},
            "category_name": {"type": "string", "description": "The name of the service category (e.g., 'food', 'tech')."},
            "pricing_model": {"type": "string", "enum": ["flat", "time_based"], "description": "The pricing model for the service."},
            "currency": {"type": "string", "description": "The currency for the price (e.g., USD)."},
            "base_price": {"type": "number", "description": "The base price of the service."}
        },
        "required": ["business_name", "name", "description", "category_name", "pricing_model", "currency", "base_price"],
    },},},
    # --- END CORRECTION ---
]

AVAILABLE_TOOLS = {
    "browse_services": be.list_services,
    "list_categories": be.list_categories,
    "create_service": be.create_service,
}

def _safe_json_dumps(obj: Any) -> str:
    try: return json.dumps(obj, ensure_ascii=False, default=repr)
    except Exception: return json.dumps(str(obj), ensure_ascii=False)

def _get_tool_call_id(tc: Any) -> str:
    if hasattr(tc, "id"): return getattr(tc, "id", "") or ""
    if hasattr(tc, "model_dump"): return (tc.model_dump() or {}).get("id", "") or ""
    if isinstance(tc, dict): return tc.get("id", "") or ""
    return ""

def _extract_tool_call_components(tc: Any) -> Tuple[Optional[str], Optional[str], str]:
    try:
        if hasattr(tc, "function"):
            fn = tc.function
            return _get_tool_call_id(tc), getattr(fn, "name", None), (getattr(fn, "arguments", "") or "{}")
        if hasattr(tc, "model_dump"):
            d = tc.model_dump() or {}
            fn = d.get("function") or {}
            return d.get("id", ""), fn.get("name"), (fn.get("arguments") or "{}")
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            return tc.get("id", ""), fn.get("name"), (fn.get("arguments") or "{}")
    except Exception: pass
    return None, None, "{}"

def _extract_tool_call(tc: Any) -> Tuple[Optional[str], Dict]:
    _, name, args_raw = _extract_tool_call_components(tc)
    try: args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
    except Exception: args = {}
    return name, args

async def _maybe_decide_intent(text: str, lang_hint: Optional[str]) -> Optional[Dict[str, Any]]:
    try: from app.intent.engine import decide_intent
    except Exception as e:
        logger.warning("Intent engine import failed: %s", e)
        return None
    try:
        if inspect.iscoroutinefunction(decide_intent): return await decide_intent(text, lang_hint)
        res = decide_intent(text, lang_hint)
        if inspect.isawaitable(res): res = await res
        return res
    except Exception as e:
        logger.exception("decide_intent failed: %s", e)
        return None

async def _run_tool(fn: Any, user_id: str, payload: Dict[str, Any]) -> Any:
    try:
        if inspect.iscoroutinefunction(fn):
            try: return await fn(user_id=user_id, **(payload or {}))
            except TypeError: return await fn(user_id, **(payload or {}))
        else:
            res = None
            try: res = fn(user_id=user_id, **(payload or {}))
            except TypeError: res = fn(user_id, **(payload or {}))
            if inspect.isawaitable(res): res = await res
            return res
    except Exception as e:
        logger.exception("Tool execution failed (%s): %s", getattr(fn, "__name__", "tool"), e)
        return {"error": str(e)}

async def handle_message(user_id: str, text: str, channel: str = "http") -> Tuple[bool, str]:
    messages = CHAT_HISTORY.setdefault(user_id, [])
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYS_PROMPT})
    if USE_INTENT_ENGINE:
        hint = await _maybe_decide_intent(text, None)
        if hint: messages.append({"role": "system", "content": f"[intent_hint]{_safe_json_dumps(hint)}"})
    messages.append({"role": "user", "content": text})
    llm = LLMClient()
    reply = await llm.get_agent_response(messages, TOOLS)
    tool_calls = getattr(reply, "tool_calls", None) or (getattr(reply, "additional_kwargs", {}) or {}).get("tool_calls")
    if tool_calls:
        assistant_tc_list: List[Dict[str, Any]] = []
        for tc in tool_calls:
            tc_id, tc_name, tc_args_raw = _extract_tool_call_components(tc)
            if not tc_name: continue
            assistant_tc_list.append({"id": tc_id or "", "type": "function", "function": {"name": tc_name, "arguments": tc_args_raw or "{}"},})
        messages.append({"role": "assistant", "content": getattr(reply, "content", None) or "", "tool_calls": assistant_tc_list,})
        for tc in tool_calls:
            tc_id, tc_name, _tc_args_raw = _extract_tool_call_components(tc)
            name, payload = _extract_tool_call(tc)
            if not name: continue
            fn = AVAILABLE_TOOLS.get(name)
            if not fn:
                messages.append({"role": "tool", "tool_call_id": tc_id or "", "content": _safe_json_dumps({"error": f"unknown tool: {name}"}),})
                continue
            result = await _run_tool(fn, user_id=user_id, payload=payload or {})
            messages.append({"role": "tool", "tool_call_id": tc_id or "", "content": _safe_json_dumps(result),})
        reply = await llm.get_agent_response(messages, TOOLS)
    final_text = getattr(reply, "content", None) or str(reply)
    messages.append({"role": "assistant", "content": final_text})
    return True, final_text