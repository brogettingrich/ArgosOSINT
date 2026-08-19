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

COUNTRY_CODES = {
    "israel": "il", "il": "il", "israel": "il",
    "usa": "us", "us": "us", "united states": "us", "america": "us",
    "uk": "uk", "united kingdom": "uk", "great britain": "uk", "england": "uk",
    "canada": "ca", "ca": "ca",
    "germany": "de", "de": "de", "deutschland": "de",
    "france": "fr", "fr": "fr",
    "brazil": "br", "br": "br", "brasil": "br",
    "spain": "es", "es": "es", "espana": "es",
    "italy": "it", "it": "it", "italia": "it",
    "russia": "ru", "ru": "ru",
    "australia": "au", "au": "au",
    "india": "in", "in": "in",
    "japan": "jp", "jp": "jp"
}

def clean_username(raw: str) -> str:
    return raw.strip().lower()

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

def generate_permutations(
    seed: str, 
    real_names: str = "", 
    location: str = "", 
    max_variations: int = 50, 
    include_digits: bool = False
) -> List[Dict[str, Any]]:
    seed_clean = clean_username(seed)
    if not seed_clean:
        return []

    results: Dict[str, Dict[str, Any]] = {}

    def add_var(name: str, rule: str, priority: int = 3):
        if not name or len(name) < 2 or len(name) > 32:
            return
        clean_n = name.strip().lower()
        if clean_n not in results:
            dist = calculate_levenshtein(seed_clean, clean_n)
            max_len = max(len(seed_clean), len(clean_n))
            similarity = round(1.0 - (dist / max_len), 2) if max_len > 0 else 1.0
            results[clean_n] = {
                "username": clean_n,
                "rule": rule,
                "priority": 0 if clean_n == seed_clean else priority,
                "distance": dist,
                "similarity": similarity,
                "is_seed": (clean_n == seed_clean)
            }

    # 1. Exact Seed
    add_var(seed_clean, "exact_seed", priority=0)

    # 2. Context Clue: Name Decomposition & Syllable Injections (e.g. ozalmagor -> oz_almagor, oz.almagor)
    name_pairs = []
    if real_names:
        for name_part in real_names.split(","):
            parts = [w.strip().lower() for w in re.split(r'[\s._\-]+', name_part) if w.strip()]
            if len(parts) >= 2:
                name_pairs.append((parts[0], parts[1]))

    # Syllable splitting for handles without punctuation (e.g. ozalmagor -> oz + almagor)
    if len(seed_clean) >= 5 and not any(c in seed_clean for c in '._-'):
        for split_idx in [2, 3, 4]:
            if split_idx < len(seed_clean) - 2:
                p1 = seed_clean[:split_idx]
                p2 = seed_clean[split_idx:]
                name_pairs.append((p1, p2))

    for p1, p2 in name_pairs:
        add_var(f"{p1}_{p2}", "name_split_underscore", priority=1)
        add_var(f"{p1}.{p2}", "name_split_dot", priority=1)
        add_var(f"{p1}-{p2}", "name_split_hyphen", priority=1)
        add_var(f"{p2}_{p1}", "name_split_inverted", priority=1)
        add_var(f"{p2}.{p1}", "name_split_inverted_dot", priority=1)
        add_var(f"{p1[0]}_{p2}", "initial_underscore", priority=2)
        add_var(f"{p1[0]}.{p2}", "initial_dot", priority=2)
        add_var(f"{p1}_{p2[0]}", "last_initial_underscore", priority=2)
        add_var(f"{p1}.{p2[0]}", "last_initial_dot", priority=2)

    # 3. Context Clue: Country / Location Suffixes & Prefixes (e.g. israel -> _il, .il, il_)
    if location:
        loc_clean = location.strip().lower()
        cc = COUNTRY_CODES.get(loc_clean, loc_clean[:2] if len(loc_clean) <= 3 else "")
        if cc:
            add_var(f"{seed_clean}_{cc}", "country_suffix_underscore", priority=1)
            add_var(f"{seed_clean}.{cc}", "country_suffix_dot", priority=1)
            add_var(f"{cc}_{seed_clean}", "country_prefix_underscore", priority=1)
            add_var(f"{seed_clean}{cc}", "country_suffix_concat", priority=2)
            for p1, p2 in name_pairs[:2]:
                add_var(f"{p1}_{p2}_{cc}", "name_country_suffix", priority=1)
                add_var(f"{p1}.{p2}.{cc}", "name_country_dot_suffix", priority=1)

    # 4. Trailing Character Doubling / Elongation (e.g. account_loading -> account_loadingg)
    last_char = seed_clean[-1]
    if last_char.isalpha():
        add_var(f"{seed_clean}{last_char}", "trailing_double_char", priority=2)
        add_var(f"{seed_clean}{last_char}{last_char}", "trailing_triple_char", priority=2)

    # 5. Separator Swaps & Removals (_ vs . vs -)
    if '.' in seed_clean and '_' not in seed_clean:
        add_var(seed_clean.replace('.', '_'), "dot_to_underscore", priority=1)
        add_var(seed_clean.replace('.', '-'), "dot_to_hyphen", priority=2)
        add_var(seed_clean.replace('.', ''), "remove_dots", priority=2)

    if '_' in seed_clean and '.' not in seed_clean:
        add_var(seed_clean.replace('_', '.'), "underscore_to_dot", priority=1)
        add_var(seed_clean.replace('_', '-'), "underscore_to_hyphen", priority=2)
        add_var(seed_clean.replace('_', ''), "remove_underscores", priority=2)

    # 6. Word-boundary elongation (e.g. account_loading -> account_loadingg, accountt_loading)
    parts = re.split(r'([._\\-])', seed_clean)
    if len(parts) > 1:
        first_word = parts[0]
        if first_word and first_word[-1].isalpha():
            add_var(first_word + first_word[-1] + "".join(parts[1:]), "first_word_elongation", priority=2)
        last_word = parts[-1]
        if last_word and last_word[-1].isalpha():
            add_var("".join(parts[:-1]) + last_word + last_word[-1], "last_word_elongation", priority=2)

    # 7. Collision Fallbacks & Digit Appends (e.g. account.loading3, account_loading1)
    base_stems = [seed_clean]
    if '.' in seed_clean:
        base_stems.append(seed_clean.replace('.', '_'))
    elif '_' in seed_clean:
        base_stems.append(seed_clean.replace('_', '.'))
    for p1, p2 in name_pairs[:2]:
        base_stems.append(f"{p1}_{p2}")
        base_stems.append(f"{p1}.{p2}")

    for base in base_stems[:3]:
        for d in ['1', '2', '3', '7', '9', '01', '99']:
            add_var(f"{base}{d}", "collision_digit", priority=2)
            add_var(f"{base}_{d}", "collision_digit_underscore", priority=2)
            add_var(f"{base}.{d}", "collision_digit_dot", priority=2)

    sorted_vars = sorted(
        results.values(),
        key=lambda x: (x["priority"], not x["is_seed"], -x["similarity"], x["distance"])
    )
    return sorted_vars[:max_variations]