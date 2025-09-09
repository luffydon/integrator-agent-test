import os
import logging
import inspect
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Adjust these imports to your actual module names
try:
    from .rules import rules_decide
except Exception:
    async def rules_decide(message: str, lang_hint: Optional[str] = None) -> Dict[str, Any]:
        return {"intent": "unknown", "confidence": 0.0, "language": lang_hint or "und"}

# Try both common names for the LLM classifier
_classify_llm_fn = None
try:
    from .llm import classify_with_llm as _classify_llm_fn  # preferred
except Exception:
    try:
        from .llm import _classify_with_llm as _classify_llm_fn  # legacy
    except Exception:
        _classify_llm_fn = None


async def _call_maybe_async(fn, *args, **kwargs):
    if fn is None:
        return None
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        res = fn(*args, **kwargs)
        if inspect.isawaitable(res):
            res = await res
        return res
    except Exception as e:
        logger.exception("Helper call failed: %s", e)
        return None


async def decide_intent(message: str, lang_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Rules-first; LLM fallback. Never blocks event loop and never raises.
    """
    try:
        rules_threshold = float(os.getenv("INTENT_MIN_CONF", "0.55"))
        llm_threshold = float(os.getenv("LLM_ACCEPT_CONF", "0.70"))
        use_llm = os.getenv("INTENT_USE_LLM", "true").lower() == "true"

        # 1) Rules
        rules_res = await _call_maybe_async(rules_decide, message, lang_hint=lang_hint)
        if rules_res and (rules_res.get("confidence", 0.0) >= rules_threshold):
            rules_res.setdefault("source", "rules")
            return rules_res

        # 2) LLM fallback
        if use_llm and _classify_llm_fn:
            llm_res = await _call_maybe_async(_classify_llm_fn, message, lang_hint=lang_hint)
            if llm_res and (llm_res.get("confidence", 0.0) >= llm_threshold):
                llm_res.setdefault("source", "llm")
                return llm_res

    except Exception as e:
        logger.exception("decide_intent failed: %s", e)
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "language": lang_hint or "und",
            "need_clarification": True,
            "next_questions": [],
            "source": "error",
            "error": str(e),
        }

    # 3) Fallback
    return {
        "intent": "unknown",
        "confidence": 0.0,
        "language": lang_hint or "und",
        "need_clarification": True,
        "next_questions": [],
        "source": "fallback",
    }
