import re
from typing import List, Dict, Any

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

COMMON_PREFIXES = ['real', 'official', 'the', 'its', 'iam', 'im']
COMMON_SUFFIXES = ['_', '__', '.', 'dev', 'yt', 'tv', 'official', 'real', '123', '01', '99', 'x', 'xx']

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

def generate_permutations(seed: str, max_variations: int = 50) -> List[Dict[str, Any]]:
    """
    Generates an exhaustive fuzzy permutation matrix:
    - Trailing letter doubling (loading -> loadingg, loadinggg)
    - Internal character elongation (ninja -> ninjaa, ninnja)
    - Dot compression & separator swaps (_ vs . vs -)
    - Number extraction and shifting
    - Suffix/Prefix additions
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

    # 2. Trailing Character Doubling / Elongation (e.g. account_loading -> account_loadingg, account_loadinggg)
    last_char = seed_clean[-1]
    if last_char.isalpha():
        add_var(f"{seed_clean}{last_char}", "trailing_double_char")
        add_var(f"{seed_clean}{last_char}{last_char}", "trailing_triple_char")

    # 3. Repeated Dot / Punctuation Compression
    if re.search(r'\.{2,}', seed_clean):
        add_var(re.sub(r'\.{2,}', '..', seed_clean), "double_dot")
        add_var(re.sub(r'\.{2,}', '.', seed_clean), "single_dot")
        add_var(re.sub(r'\.+', '', seed_clean), "stripped_dots")
        add_var(re.sub(r'\.+', '_', seed_clean), "dots_to_underscore")
        add_var(re.sub(r'\.+', '-', seed_clean), "dots_to_hyphen")

    # 4. Separator Swaps & Removals (_ vs . vs -)
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

    # 5. Word-boundary / Internal letter doubling for multi-word handles (e.g., account_loading -> account_loadingg, accountt_loading)
    parts = re.split(r'([._\-])', seed_clean)
    if len(parts) > 1:
        # Doubled last char of first word
        first_word = parts[0]
        if first_word and first_word[-1].isalpha():
            mod_first = first_word + first_word[-1]
            add_var(mod_first + "".join(parts[1:]), "first_word_elongation")
        # Doubled last char of last word
        last_word = parts[-1]
        if last_word and last_word[-1].isalpha():
            mod_last = last_word + last_word[-1]
            add_var("".join(parts[:-1]) + mod_last, "last_word_elongation")

    # 6. Digit Separation & Zero-padding
    num_match = re.search(r'^(.*?)(\d+)$', seed_clean)
    if num_match:
        stem, num = num_match.groups()
        if stem:
            add_var(f"{stem}_{num}", "separated_digits_underscore")
            add_var(f"{stem}.{num}", "separated_digits_dot")
            if len(num) == 1:
                add_var(f"{stem}0{num}", "zero_padded_num")
                add_var(f"{stem}_0{num}", "zero_padded_num_underscore")

    # 7. Common Suffixes & Prefixes
    stripped = seed_clean.strip('._-')
    if stripped and stripped != seed_clean:
        add_var(stripped, "stripped_edges")

    if len(seed_clean) <= 16:
        for pre in COMMON_PREFIXES[:4]:
            add_var(f"{pre}_{stripped or seed_clean}", "prefix_addition")
            add_var(f"{pre}.{stripped or seed_clean}", "prefix_dot_addition")
        for suf in COMMON_SUFFIXES[:6]:
            add_var(f"{stripped or seed_clean}{suf}", "suffix_addition")

    # 8. Leetspeak variations
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

    sorted_vars = sorted(
        results.values(),
        key=lambda x: (not x["is_seed"], -x["similarity"], x["distance"])
    )
    return sorted_vars[:max_variations]