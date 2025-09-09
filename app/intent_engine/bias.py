from typing import Dict, Optional
def apply_session_bias(scores: Dict[str, Dict], selected_agent: Optional[str]) -> Dict[str, Dict]:
    if not selected_agent: return scores
    top_domain = max(scores.keys(), key=lambda d: scores[d]["score"])
    top_score = scores[top_domain]["score"]
    if 0.60 <= top_score <= 0.89 and top_domain == selected_agent:
        scores[top_domain]["score"] = min(0.90, top_score + 0.10)
        scores[top_domain]["signals"].append("session_bias")
    return scores
