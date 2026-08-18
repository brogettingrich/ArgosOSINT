import re
from typing import Dict, Any, List

def tokenize_text(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words."""
    if not text:
        return []
    words = re.findall(r'[a-zA-Z0-9]{3,}', text.lower())
    # Exclude ultra-common web stop words
    stop_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'user', 'profile', 'page', 'online'}
    return [w for w in words if w not in stop_words]

def compute_jaccard_similarity(tokens1: List[str], tokens2: List[str]) -> float:
    """Calculate Jaccard similarity index between token sets."""
    s1, s2 = set(tokens1), set(tokens2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1.intersection(s2))
    union = len(s1.union(s2))
    return round(intersection / union, 2) if union > 0 else 0.0

def score_profile_corroboration(seed_info: Dict[str, Any], candidate_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a correlation score and evidence tags between a target seed and a discovered profile.
    Checks:
    - Username similarity
    - Display Name match
    - Bio keywords overlap
    - Location match
    - Avatar/Image presence
    """
    score = 0.0
    evidence = []

    seed_user = (seed_info.get("username") or "").lower()
    cand_user = (candidate_info.get("username") or "").lower()

    # 1. Username Match / Similarity (Up to 45 pts)
    if seed_user == cand_user:
        score += 45
        evidence.append("Exact Username Match")
    else:
        # Check if stripped match
        s_strip = re.sub(r'[\._\-]', '', seed_user)
        c_strip = re.sub(r'[\._\-]', '', cand_user)
        if s_strip == c_strip:
            score += 38
            evidence.append("Punctuation-Stripped Exact Match")
        elif s_strip in c_strip or c_strip in s_strip:
            score += 25
            evidence.append("Sub-Handle Variation")
        else:
            score += 15
            evidence.append("Fuzzy Permutation")

    # 2. Display Name Match (Up to 30 pts)
    seed_name = (seed_info.get("display_name") or seed_info.get("real_name") or "").strip().lower()
    cand_name = (candidate_info.get("display_name") or candidate_info.get("title") or "").strip().lower()

    if seed_name and cand_name:
        if seed_name == cand_name:
            score += 30
            evidence.append("Exact Display Name Match")
        elif seed_name in cand_name or cand_name in seed_name:
            score += 20
            evidence.append("Partial Name Match")

    # 3. Bio / Keyword Similarity (Up to 25 pts)
    seed_bio = seed_info.get("bio") or seed_info.get("notes") or ""
    cand_bio = candidate_info.get("bio") or candidate_info.get("description") or ""

    if seed_bio and cand_bio:
        tok1 = tokenize_text(seed_bio)
        tok2 = tokenize_text(cand_bio)
        jaccard = compute_jaccard_similarity(tok1, tok2)
        if jaccard >= 0.5:
            score += 25
            evidence.append(f"High Bio Overlap ({int(jaccard*100)}%)")
        elif jaccard >= 0.2:
            score += 15
            evidence.append(f"Bio Keyword Overlap ({int(jaccard*100)}%)")

    # Cap score at 100
    final_score = min(100, int(score))

    if final_score >= 85:
        verdict = "CONFIRMED_MATCH"
        badge_color = "#38ef7d" # Green
    elif final_score >= 60:
        verdict = "HIGH_PROBABILITY"
        badge_color = "#4facfe" # Blue
    elif final_score >= 35:
        verdict = "POSSIBLE_MATCH"
        badge_color = "#f6d365" # Yellow
    else:
        verdict = "UNVERIFIED"
        badge_color = "#888888" # Grey

    return {
        "score": final_score,
        "verdict": verdict,
        "badge_color": badge_color,
        "evidence": evidence
    }