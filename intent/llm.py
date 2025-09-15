import os
import json
import logging
import re
import openai
from typing import Dict, Optional, Any
import asyncio

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are an intent classification assistant. Analyze the user's message and determine their intent.

Output ONLY valid JSON with the following fields:
- intent: one of "food", "real_estate", "transportation", "business", "menu", "add_service", or "unknown"
- confidence: a number between 0 and 1 representing your certainty
- language: the ISO language code of the user's message
- slots: an object containing any extracted information like time, location, people count, etc.

Guidelines:
1. Infer slots from the message but do not invent facts
2. If the user is asking for a menu or listing of services, use "menu" intent
3. If the user wants to add a new service, use "add_service" intent
4. For ambiguous cases, provide a lower confidence score
5. Always respond with valid JSON only"""

async def classify_with_llm(
    text: str, 
    lang: str, 
    rules_context: Optional[Dict] = None
) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return {"intent": "unknown", "confidence": 0.0, "language": lang, "slots": {}}
    try:
        if rules_context and rules_context.get("intent") != "unknown":
            enhanced_prompt = f"""
            {PROMPT_TEMPLATE}
            
            A preliminary analysis suggests the user might be asking about: {rules_context['intent']} 
            with {rules_context['confidence']:.2f} confidence.
            
            User message: "{text}"
            Language: {lang}
            
            Please consider this context but make your own assessment.
            """
        else:
            enhanced_prompt = f"""
            {PROMPT_TEMPLATE}
            
            User message: "{text}"
            Language: {lang}
            """
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": enhanced_prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            llm_response = response.choices[0].message.content.strip()
        except ImportError:
            response = await openai.ChatCompletion.acreate(
                model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": enhanced_prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            llm_response = response.choices[0].message.content.strip()
        try:
            result = json.loads(llm_response)
            if not all(key in result for key in ["intent", "confidence", "language", "slots"]):
                raise json.JSONDecodeError("Missing required fields", llm_response, 0)
            result.setdefault("intent", "unknown")
            result.setdefault("confidence", 0.0)
            result.setdefault("language", lang)
            result.setdefault("slots", {})
            return result
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON: %s", llm_response)
            return _parse_llm_fallback(llm_response, lang)
    except Exception as e:
        logger.exception("LLM classification failed: %s", e)
        return {"intent": "unknown", "confidence": 0.0, "language": lang, "slots": {}}

def _parse_llm_fallback(response_text: str, lang: str) -> Dict[str, Any]:
    intent_patterns = {
        'food': r'\b(food|restaurant|meal|eat|dining)\b',
        'real_estate': r'\b(real estate|rent|apartment|house|property)\b',
        'transportation': r'\b(transport|taxi|ride|bus|car)\b',
        'business': r'\b(business|service|company|enterprise)\b',
        'menu': r'\b(menu|help|start|categories)\b',
        'add_service': r'\b(add|create|new)\s+service\b'
    }
    detected_intent = "unknown"
    for intent, pattern in intent_patterns.items():
        if re.search(pattern, response_text, re.IGNORECASE):
            detected_intent = intent
            break
    return {"intent": detected_intent, "confidence": 0.6 if detected_intent != "unknown" else 0.0, "language": lang, "slots": {}, "llm_fallback": True}
