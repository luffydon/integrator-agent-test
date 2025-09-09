from typing import Dict, Any
from .loader import load_configs
from .rules import score_domains
from .bias import apply_session_bias
from .slots import basic_slot_hints
from .llm import LLMClient
from pathlib import Path
import json

def decide_intent(message: str, session: Dict[str,Any]=None, enable_llm=False) -> Dict[str,Any]:
    cfg = load_configs()
    aliases = cfg["aliases"]; weights = cfg["weights"]["weights"]; th = cfg["weights"]["thresholds"]; neg = cfg["negations"]
    session = session or {}; selected = session.get("selected_agent"); locale = session.get("locale","en")
    scores = score_domains(message, aliases, neg, weights)
    scores = apply_session_bias(scores, selected)
    top = max(scores.keys(), key=lambda d: scores[d]["score"]); top_score = scores[top]["score"]
    entities = basic_slot_hints(message, locale)

    if top_score >= th["route_strong"]:
        return {"handled": True, "intent": top, "action": None, "entities": entities, "target_agent": top, "confidence": round(top_score,3), "rationale":"rules_strong", "followup_question": None}

    if th["route_candidate_low"] <= top_score <= th["route_candidate_high"] and selected == top:
        return {"handled": True, "intent": top, "action": None, "entities": entities, "target_agent": top, "confidence": round(min(0.9, top_score+0.1),3), "rationale":"rules_candidate_session_biased", "followup_question": None}

    if enable_llm:
        # ⬇️ --- THIS IS THE CORRECTED LINE --- ⬇️
        prompt = (Path(__file__).resolve().parent / "prompts" / "intent_hybrid_prompt_v2.txt").read_text(encoding="utf-8")
        try:
            out = LLMClient().classify(prompt, message, extra={"session": session, "rules_top": {"domain": top, "score": top_score}})
            return {"handled": bool(out.get("handled", True)), "intent": out.get("intent","fallback"), "action": out.get("action"),
                    "entities": out.get("entities") or {}, "target_agent": out.get("target_agent") or out.get("intent"),
                    "confidence": float(out.get("confidence", 0.6)), "rationale": out.get("rationale"), "followup_question": out.get("followup_question")}
        except Exception as e:
            return {"handled": False, "intent": "fallback", "action": None, "entities": entities, "target_agent": None, "confidence": 0.0, "rationale": f"llm_error:{e}", "followup_question": "Please clarify what you need."}

    return {"handled": False, "intent": "fallback", "action": None, "entities": entities, "target_agent": None, "confidence": round(top_score,3), "rationale":"rules_low", "followup_question":"Please clarify what you need."}