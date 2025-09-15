import os
import logging
import inspect
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

try:
    from .rules import match_rules
except ImportError as e:
    logger.warning("Failed to import rules module: %s", e)
    async def match_rules(message: str, lang_hint: Optional[str] = None) -> Dict[str, Any]:
        return {"intent": "unknown", "confidence": 0.0, "language": lang_hint or "en", "slots": {}}

try:
    from .llm import classify_with_llm
except ImportError as e:
    logger.warning("Failed to import LLM module: %s", e)
    classify_with_llm = None

try:
    from .slots import refine_slots
except ImportError as e:
    logger.warning("Failed to import slots module: %s", e)
    def refine_slots(text: str, lang: str, intent: str, base_slots: Dict) -> Dict:
        return base_slots or {}

async def _call_maybe_async(fn, *args, **kwargs):
    if fn is None:
        return None
    try:
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        result = fn(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result
    except Exception as e:
        logger.exception("Function call failed: %s", e)
        return None

async def decide_intent(message: str, lang_hint: Optional[str] = None) -> Dict[str, Any]:
    rules_threshold = float(os.getenv("RULES_MIN_CONF", "0.65"))
    llm_threshold = float(os.getenv("LLM_MIN_CONF", "0.75"))
    use_llm = os.getenv("USE_LLM_FALLBACK", "true").lower() == "true"
    lang = lang_hint or "en"
    result = {"intent": "unknown","confidence": 0.0,"language": lang,"slots": {},"source": "fallback","need_clarification": True}
    try:
        rules_result = await _call_maybe_async(match_rules, message, lang)
        if rules_result.get("confidence", 0.0) >= rules_threshold:
            result.update(rules_result)
            result["source"] = "rules"
            result["need_clarification"] = False
            result["slots"] = refine_slots(message, result["language"], result["intent"], result["slots"])
            return result
        if use_llm and classify_with_llm:
            llm_result = await _call_maybe_async(classify_with_llm, message, lang, rules_context=rules_result)
            if llm_result and llm_result.get("confidence", 0.0) >= llm_threshold:
                result.update(llm_result)
                result["source"] = "llm"
                result["need_clarification"] = False
                result["slots"] = refine_slots(message, result["language"], result["intent"], result.get("slots", {}))
                return result
        if rules_result.get("confidence", 0.0) > 0.3:
            result.update(rules_result)
            result["need_clarification"] = True
            result["clarification_question"] = _generate_clarification_question(rules_result["intent"], lang)
        return result
    except Exception as e:
        logger.exception("Intent classification failed: %s", e)
        result["error"] = str(e)
        return result

def _generate_clarification_question(intent: str, lang: str) -> str:
    questions = {'en': {'food': "Are you looking for food delivery or restaurant options?",'real_estate': "Are you looking to rent or find real estate?",'transportation': "Do you need a taxi, ride, or other transportation?",'business': "Are you inquiring about business services?",'unknown': "Could you please clarify what you're looking for?"},'ru': {'food': "Вы ищете доставку еды или варианты ресторанов?",'real_estate': "Вы хотите снять жилье или найти недвижимость?",'transportation': "Вам нужно такси, поездка или другой транспорт?",'business': "Вы интересуетесь бизнес-услугами?",'unknown': "Не могли бы вы уточнить, что вы ищете?"}}
    lang_questions = questions.get(lang, questions['en'])
    return lang_questions.get(intent, lang_questions['unknown'])
