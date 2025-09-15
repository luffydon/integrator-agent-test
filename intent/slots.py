from __future__ import annotations
import re
from typing import Dict, Any

TIME_PATTERNS = {
    'en': re.compile(r'(?i)\b(now|today|tonight|tomorrow|\d{1,2}:\d{2}|\d{1,2}[ap]m?)\b'),
    'ru': re.compile(r'(?i)\b(сейчас|сегодня|сегодня вечером|завтра|\d{1,2}:\d{2})\b'),
}

PEOPLE_PAT = re.compile(r'(?i)(?:for|для|für)?\s*(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons|человек|людей|người|personen|명)')
LOCATION_PAT = re.compile(r'(?i)\b(in|at|в|bei|nach|에서)\s+([^\d.,!?;:]+?)(?=\s|$|[.,!?;:])')
TERM_PAT = re.compile(r'(?i)(short\s*-?term|long\s*-?term|на\s*короткий\s*срок|долгосрочно|ngắn\s*hạn|dài\s*hạn|kurzfristig|langfristig)')

def refine_slots(text: str, lang: str, intent: str, base_slots: Dict) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return base_slots or {}
    slots = dict(base_slots or {})
    t = text.lower()
    time_pattern = TIME_PATTERNS.get(lang, TIME_PATTERNS['en'])
    time_match = time_pattern.search(t)
    if time_match:
        slots['time'] = time_match.group(0)
    people_match = PEOPLE_PAT.search(t)
    if people_match:
        try:
            people_count = people_match.group(1)
            word_to_digit = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
            slots['people'] = word_to_digit.get(people_count, int(people_count) if people_count.isdigit() else None)
            if slots['people'] is None:
                slots.pop('people', None)
        except (ValueError, IndexError):
            pass
    location_match = LOCATION_PAT.search(t)
    if location_match:
        slots['location'] = location_match.group(2).strip()
    term_match = TERM_PAT.search(t)
    if term_match:
        term = term_match.group(1).lower()
        if any(kw in term for kw in ['short','корот','ngắn','kurz']):
            slots['term'] = 'short-term'
        else:
            slots['term'] = 'long-term'
    if intent == 'food':
        cuisine_match = re.search(r'(?i)\b(italian|chinese|mexican|japanese|vegan|vegetarian|gluten-free)\b', t)
        if cuisine_match:
            slots['cuisine'] = cuisine_match.group(0).lower()
    elif intent == 'real_estate':
        property_match = re.search(r'(?i)\b(apartment|house|studio|condo|loft|penthouse)\b', t)
        if property_match:
            slots['property_type'] = property_match.group(0).lower()
    return slots
