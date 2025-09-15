from __future__ import annotations
import re
from typing import Dict, Any

LEX = {
    'en': {
        'food': ['food', 'eat', 'restaurant', 'menu', 'delivery', 'order', 'meal', 'dinner', 'lunch', 'breakfast', 'cuisine'],
        'real_estate': ['rent', 'apartment', 'flat', 'house', 'lease', 'real estate', 'property', 'accommodation', 'room', 'studio'],
        'transportation': ['taxi', 'ride', 'bus', 'train', 'airport', 'uber', 'lyft', 'transport', 'car', 'vehicle'],
        'business': ['service', 'company', 'invoice', 'payment', 'booking', 'categories', 'business', 'enterprise', 'commercial'],
        'menu': ['menu', 'help', 'start', 'what can you do', 'options', 'services'],
        'add_service': ['add service', 'create service', 'new service', 'register service']
    },
    'ru': {
        'food': ['еда', 'поесть', 'ресторан', 'меню', 'доставка', 'заказать', 'кухня', 'ужин', 'обед', 'завтрак'],
        'real_estate': ['аренда', 'квартира', 'дом', 'жильё', 'снять', 'недвижимость', 'помещение', 'комната'],
        'transportation': ['такси', 'поездка', 'автобус', 'поезд', 'аэропорт', 'транспорт', 'машина'],
        'business': ['услуга', 'компания', 'счёт', 'оплата', 'бронь', 'категории', 'бизнес', 'предприятие'],
        'menu': ['меню', 'помощь', 'старт', 'что ты умеешь', 'опции', 'сервисы'],
        'add_service': ['добавить услугу', 'создать услугу', 'новая услуга']
    }
}

COMMAND_PATTERNS = {
    'menu': re.compile(r'(?i)^/(menu|start|help)$|^(menu|categories|help|what can you do)'),
    'add_service': re.compile(r'(?i)(add service|create service|new service|добавить услугу|создать услугу|новая услуга)'),
}

def match_rules(text: str, lang: str) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return {"intent": "unknown", "confidence": 0.0, "language": lang, "slots": {}}
    t = text.lower().strip()
    for command, pattern in COMMAND_PATTERNS.items():
        if pattern.search(t):
            return {"intent": command, "confidence": 0.95, "language": lang, "slots": {}, "source": "rules_command"}
    bag = LEX.get(lang, LEX['en'])
    best_intent, best_confidence = "unknown", 0.0
    for intent, words in bag.items():
        hits = sum(1 for w in words if re.search(r'\b' + re.escape(w) + r'\b', t))
        if hits > 0:
            confidence = min(0.3 + (hits * 0.15), 0.9)
            if confidence > best_confidence:
                best_intent, best_confidence = intent, confidence
    slots = extract_basic_slots(t, lang)
    return {"intent": best_intent, "confidence": best_confidence, "language": lang, "slots": slots, "source": "rules_keywords"}

def extract_basic_slots(text: str, lang: str) -> Dict[str, Any]:
    slots = {}
    time_patterns = {
        'en': r'\b(now|today|tonight|tomorrow|\d{1,2}:\d{2}|\d{1,2}[ap]m?)\b',
        'ru': r'\b(сейчас|сегодня|сегодня вечером|завтра|\d{1,2}:\d{2})\b',
    }
    pattern = time_patterns.get(lang, time_patterns['en'])
    time_match = re.search(pattern, text, re.IGNORECASE)
    if time_match:
        slots['time'] = time_match.group(0)
    people_pattern = r'(?i)(?:for|для|für)?\s*(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons|человек|людей)'
    people_match = re.search(people_pattern, text, re.IGNORECASE)
    if people_match:
        try:
            people_count = people_match.group(1)
            word_to_digit = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
            slots['people'] = word_to_digit.get(people_count, int(people_count) if people_count.isdigit() else None)
            if slots['people'] is None:
                slots.pop('people', None)
        except (ValueError, IndexError):
            pass
    return slots
