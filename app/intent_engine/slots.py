from typing import Dict
NOW = {"en":["now"],"ru":["сейчас"],"vi":["bây giờ"],"de":["jetzt"],"ko":["지금"]}
LATER = {"en":["later"],"ru":["позже"],"vi":["sau"],"de":["später"],"ko":["나중"]}
def basic_slot_hints(message: str, locale: str) -> Dict[str,str]:
    loc = (locale or "en").split("-")[0]; m = (message or "").lower(); ents = {}
    if any(w in m for w in NOW.get(loc, [])): ents["time"] = "now"
    if any(w in m for w in LATER.get(loc, [])): ents["time"] = "later"
    if any(w in m for w in ["delivery","доставка","giao hàng","lieferung","배달"]): ents["mode"] = "delivery"
    if any(w in m for w in ["visit","go","посетить","đến","besuchen","방문"]): ents.setdefault("mode", "visit")
    return ents
