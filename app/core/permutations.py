import re
from typing import List, Set, Dict, Any

LEET_MAP = {
    'o': ['0'],
    '0': ['o'],
    'i': ['1', 'l'],
    'l': ['1', 'i'],
    '1': ['i', 'l'],
    'e': ['3'],
    '3': ['e'],
    'a': ['4', '@'],
    's': ['5', '$'],
    '5': ['s'],
    't': ['7'],
    '7': ['t'],
}

COMMON_PREFIXES = ['real', 'official', 'the', 'its', 'iam']
COMMON_SUFFIXES = ['_', '__', '.', 'dev', 'yt', 'tv', 'official', 'real', '123', '01', '99']

def clean_username(raw: str) -> str:
    """Strip whitespace and lowercase."""
    return raw.strip().lower()

def calculate_levenshtein(s1: str, s2: str) -> int:
    """Standard Levenshtein edit distance."""
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

def generate_permutations(seed: str, max_variations: int = 40) -> List[Dict[str, Any]]:
    """
    Generates intelligent fuzzy permutations for a username.
    Handles dot compression (user...34 -> user..34, user.34),
    separator substitution (_ vs . vs -), leetspeak, and padding.
    """
    seed_clean = clean_username(seed)
    if not seed_clean:
        return []

    results: Dict[str, Dict[str, Any]] = {}

    def add_var(name: str, rule: str):
        if not name or len(name) < 2 or len(name) > 32:
            return
        if name not in results:
            dist = calculate_levenshtein(seed_clean, name)
            # Similarity ratio (0.0 to 1.0)
            max_len = max(len(seed_clean), len(name))
            similarity = round(1.0 - (dist / max_len), 2)
            results[name] = {
                "username": name,
                "rule": rule,
                "distance": dist,
                "similarity": similarity,
                "is_seed": (name == seed_clean)
            }

    # 1. Exact Seed
    add_var(seed_clean, "exact_seed")

    # 2. Repeated Dot / Punctuation Compression & Variations
    # e.g., user...34 -> user..34, user.34, user34
    if re.search(r'\.{2,}', seed_clean):
        # 2 dots
        add_var(re.sub(r'\.{2,}', '..', seed_clean), "double_dot")
        # 1 dot
        add_var(re.sub(r'\.{2,}', '.', seed_clean), "single_dot")
        # stripped dot
        add_var(re.sub(r'\.+', '', seed_clean), "stripped_dots")
        # replace dots with underscore or hyphen
        add_var(re.sub(r'\.+', '_', seed_clean), "dots_to_underscore")
        add_var(re.sub(r'\.+', '-', seed_clean), "dots_to_hyphen")

    # 3. Repeated Underscores / Hyphens
    if re.search(r'_{2,}', seed_clean):
        add_var(re.sub(r'_{2,}', '_', seed_clean), "single_underscore")
        add_var(re.sub(r'_+', '.', seed_clean), "underscore_to_dot")
        add_var(re.sub(r'_+', '', seed_clean), "stripped_underscores")

    # 4. Separator swaps
    if '.' in seed_clean and '_' not in seed_clean:
        add_var(seed_clean.replace('.', '_'), "dot_to_underscore")
        add_var(seed_clean.replace('.', '-'), "dot_to_hyphen")
        add_var(seed_clean.replace('.', ''), "remove_dots")

    if '_' in seed_clean and '.' not in seed_clean:
        add_var(seed_clean.replace('_', '.'), "underscore_to_dot")
        add_var(seed_clean.replace('_', '-'), "underscore_to_hyphen")
        add_var(seed_clean.replace('_', ''), "remove_underscores")

    if '-' in seed_clean:
        add_var(seed_clean.replace('-', '_'), "hyphen_to_underscore")
        add_var(seed_clean.replace('-', '.'), "hyphen_to_dot")
        add_var(seed_clean.replace('-', ''), "remove_hyphens")

    # 5. Number extraction and shifting (e.g., user34 -> user034, user_34, user.34)
    num_match = re.search(r'^(.*?)(\d+)$', seed_clean)
    if num_match:
        stem, num = num_match.groups()
        if stem:
            # Separator before digits
            add_var(f"{stem}_{num}", "separated_digits_underscore")
            add_var(f"{stem}.{num}", "separated_digits_dot")
            # Zero-padded digits (e.g. user7 -> user07)
            if len(num) == 1:
                add_var(f"{stem}0{num}", "zero_padded_num")
                add_var(f"{stem}_0{num}", "zero_padded_num_underscore")

    # 6. Stripping trailing/leading underscores/dots
    stripped = seed_clean.strip('._-')
    if stripped and stripped != seed_clean:
        add_var(stripped, "stripped_edges")

    # 7. Common Leetspeak transforms
    leet_candidates = [seed_clean]
    for char, replacements in LEET_MAP.items():
        if char in seed_clean:
            new_cands = []
            for cand in leet_candidates[:4]:
                for r in replacements:
                    new_cands.append(cand.replace(char, r, 1))
            leet_candidates.extend(new_cands)

    for lc in set(leet_candidates):
        if lc != seed_clean:
            add_var(lc, "leetspeak_variation")

    # 8. Prefixes and Suffixes (if seed is short)
    if len(seed_clean) <= 12:
        for pre in COMMON_PREFIXES[:3]:
            add_var(f"{pre}_{stripped or seed_clean}", "prefix_addition")
        for suf in COMMON_SUFFIXES[:4]:
            add_var(f"{stripped or seed_clean}{suf}", "suffix_addition")

    # Sort by similarity descending, seed first
    sorted_vars = sorted(
        results.values(),
        key=lambda x: (not x["is_seed"], -x["similarity"], x["distance"])
    )
    return sorted_vars[:max_variations]