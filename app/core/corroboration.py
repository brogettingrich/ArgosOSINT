import re
from typing import Dict, Any, Optional

def calculate_levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return calculate_levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def score_profile_corroboration(
    seed_meta: Dict[str, Any], 
    candidate_meta: Dict[str, Any],
    location: str = ""
) -> Dict[str, Any]:
    score = 0
    factors = []

    seed_user = seed_meta.get("username", "").strip().lower()
    cand_user = candidate_meta.get("username", "").strip().lower()
    seed_name = seed_meta.get("display_name", "").strip().lower()
    cand_name = (candidate_meta.get("display_name") or candidate_meta.get("username", "")).strip().lower()
    bio = (candidate_meta.get("bio") or "").lower()

    # 1. Exact or High-Similarity Handle Match (Max 40 pts)
    if seed_user == cand_user:
        score += 40
        factors.append("Exact handle match (+40)")
    else:
        dist = calculate_levenshtein(seed_user, cand_user)
        max_l = max(len(seed_user), len(cand_user))
        sim = 1.0 - (dist / max_l) if max_l > 0 else 0
        if sim >= 0.8:
            score += 30
            factors.append(f"High phonetic handle similarity {int(sim*100)}% (+30)")
        elif sim >= 0.6:
            score += 20
            factors.append(f"Moderate handle similarity {int(sim*100)}% (+20)")

    # 2. Display Name Alignment (Max 30 pts)
    if seed_name and cand_name:
        if seed_name == cand_name and seed_name != seed_user:
            score += 30
            factors.append("Exact real name confirmation (+30)")
        elif any(part in cand_name for part in seed_name.split() if len(part) > 2):
            score += 20
            factors.append("Partial real name match (+20)")

    # 3. Location Keyword Alignment in Bio (Max 20 pts)
    if location and bio:
        loc_clean = location.strip().lower()
        if loc_clean in bio or (loc_clean == "israel" and any(k in bio for k in ["il", "tel aviv", "jerusalem", "ישראל"])):
            score += 20
            factors.append(f"Location match in bio (+20)")

    # 4. Outbound Cross-Links or Verified Badges (Max 10 pts)
    if candidate_meta.get("is_verified"):
        score += 10
        factors.append("Platform verified badge (+10)")
    if candidate_meta.get("outbound_links"):
        score += 10
        factors.append("Outbound social cross-links present (+10)")

    score = min(100, max(20, score))

    if score >= 85:
        verdict = "CONFIRMED IDENTITY"
    elif score >= 60:
        verdict = "HIGH PROBABILITY"
    else:
        verdict = "UNVERIFIED ALIAS"

    return {
        "score": score,
        "verdict": verdict,
        "factors": factors
    }