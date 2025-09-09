import re
from typing import Dict, List, Tuple
TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)
def tokenize(text: str) -> List[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]
def contains_any(tokens: List[str], words: List[str]) -> Tuple[bool, List[str]]:
    words_l = [w.lower() for w in words]
    hits = sorted(set([t for t in tokens if t in words_l]))
    return (len(hits) > 0, hits)
def substring_hits(text: str, words: List[str]) -> List[str]:
    text_l = (text or "").lower()
    hits = []
    for w in words:
        wl = w.lower()
        if wl in text_l and wl not in hits:
            hits.append(wl)
    return hits
def score_domains(text: str, aliases: Dict[str, Dict[str, List[str]]], negations: Dict[str, List[str]], weights: Dict[str, float]) -> Dict[str, Dict]:
    tokens = tokenize(text)
    scores = {}
    for domain, lists in aliases.items():
        strong = lists.get("strong", []); weak = lists.get("weak", [])
        score = 0.0; signals = []
        strong_hit, strong_tokens = contains_any(tokens, strong)
        if strong_hit: score += weights["alias_strong"]; signals.append("alias_strong")
        weak_tokens = substring_hits(text, weak)
        if weak_tokens: score += weights["alias_weak"]; signals.append("alias_weak")
        if (strong_hit or weak_tokens) and any(n in tokens for n in sum(negations.values(), [])):
            score += weights["negation"]; signals.append("negation")
        scores[domain] = {"score": max(0.0, min(1.0, score)), "signals": signals}
    strong_domains = [d for d,v in scores.items() if "alias_strong" in v["signals"]]
    if len(strong_domains) > 1:
        for d in strong_domains:
            scores[d]["score"] = max(0.0, scores[d]["score"] + weights["conflict"])
            scores[d]["signals"].append("conflict")
    return scores
