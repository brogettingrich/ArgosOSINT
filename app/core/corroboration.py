import re
from typing import Dict, Any, List

def tokenize_text(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words."""
    if not text:
        return []
    words = re.findall(r'[a-zA-Z0-9]{2,}', text.lower())
    stop_words = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'user', 'profile', 'page', 'online'}
    return [w for w in words if w not in stop_words]

def compute_jaccard_similarity(tokens1: List[str], tokens2: List[str]) -> float:
    s1, s2 = set(tokens1), set(tokens2)
    if not s1 or not s2:
        return 0.0
    intersection = len(s1.intersection(s2))
    union = len(s1.union(s2))
    return round(intersection / union, 2) if union > 0 else 0.0

def score_profile_corroboration(seed_info: Dict[str, Any], candidate_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates candidate profile against multiple comma-separated aliases and seeds.
    Returns the highest match score along with the matched alias tag.
    """
    seed_user = (seed_info.get("username") or "").strip().lower()
    cand_user = (candidate_info.get("username") or "").strip().lower()

    # Parse aliases (comma separated)
    raw_aliases = seed_info.get("display_name") or seed_info.get("real_name") or ""
    alias_list = [a.strip().lower() for a in raw_aliases.split(",") if a.strip()]
    if not alias_list and seed_user:
        alias_list = [seed_user]

    cand_name = (candidate_info.get("display_name") or candidate_info.get("title") or cand_user).strip().lower()
    cand_bio = candidate_info.get("bio") or candidate_info.get("description") or ""

    best_score = 0
    best_matched_alias = None
    best_evidence = []

    for alias in alias_list:
        score = 0
        evidence = []

        # 1. Username vs Alias / Seed Check (Up to 45 pts)
        if cand_user == seed_user:
            score += 45
            evidence.append("Exact Handle Match")
        elif cand_user == alias:
            score += 40
            evidence.append(f"Handle Matches Alias '{alias}'")
        else:
            s_strip = re.sub(r'[\._\-]', '', seed_user)
            c_strip = re.sub(r'[\._\-]', '', cand_user)
            if s_strip == c_strip:
                score += 38
                evidence.append("Stripped Punctuation Match")
            elif s_strip in c_strip or c_strip in s_strip:
                score += 25
                evidence.append("Sub-Handle Variation")
            else:
                score += 15
                evidence.append("Fuzzy Permutation")

        # 2. Display Name / Alias Similarity (Up to 35 pts)
        if alias and cand_name:
            if alias == cand_name:
                score += 35
                evidence.append(f"Exact Name Match ('{alias}')")
            elif alias in cand_name or cand_name in alias:
                score += 25
                evidence.append(f"Partial Name Match ('{alias}')")
            else:
                tok1 = tokenize_text(alias)
                tok2 = tokenize_text(cand_name)
                jacc = compute_jaccard_similarity(tok1, tok2)
                if jacc >= 0.5:
                    score += 20
                    evidence.append(f"Name Token Match ({int(jacc*100)}%)")

        # 3. Bio / Keyword Similarity (Up to 20 pts)
        seed_bio = seed_info.get("bio") or ""
        if seed_bio and cand_bio:
            tok1 = tokenize_text(seed_bio)
            tok2 = tokenize_text(cand_bio)
            jacc = compute_jaccard_similarity(tok1, tok2)
            if jacc >= 0.3:
                score += 20
                evidence.append(f"Bio Keyword Overlap ({int(jacc*100)}%)")

        if score > best_score:
            best_score = score
            best_matched_alias = alias
            best_evidence = evidence

    final_score = min(100, best_score)
    if final_score >= 80:
        verdict = "CONFIRMED_MATCH"
    elif final_score >= 50:
        verdict = "HIGH_PROBABILITY"
    else:
        verdict = "POSSIBLE_MATCH"

    return {
        "score": final_score,
        "matched_alias": best_matched_alias,
        "verdict": verdict,
        "evidence": best_evidence
    }