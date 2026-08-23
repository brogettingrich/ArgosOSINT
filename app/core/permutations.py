import re
from typing import List, Dict, Any, Optional

COUNTRY_MAPPING: Dict[str, Dict[str, Any]] = {
    "israel": {"code": "il", "name": "Israel", "aliases": ["israel", "il", "ישראל", "telaviv", "jerusalem"]},
    "united states": {"code": "us", "name": "United States", "aliases": ["usa", "us", "united states", "america"]},
    "united kingdom": {"code": "uk", "name": "United Kingdom", "aliases": ["uk", "united kingdom", "britain", "england", "gb"]},
    "new zealand": {"code": "nz", "name": "New Zealand", "aliases": ["nz", "new zealand", "new zealend", "newzealand", "kiwi", "aotearoa"]},
    "australia": {"code": "au", "name": "Australia", "aliases": ["au", "australia", "aus", "oz"]},
    "canada": {"code": "ca", "name": "Canada", "aliases": ["ca", "canada", "can"]},
    "germany": {"code": "de", "name": "Germany", "aliases": ["de", "germany", "deutschland", "ger"]},
    "france": {"code": "fr", "name": "France", "aliases": ["fr", "france", "fra"]},
    "russia": {"code": "ru", "name": "Russia", "aliases": ["ru", "russia", "rf"]},
    "brazil": {"code": "br", "name": "Brazil", "aliases": ["br", "brazil", "brasil"]},
    "spain": {"code": "es", "name": "Spain", "aliases": ["es", "spain", "espana"]},
    "italy": {"code": "it", "name": "Italy", "aliases": ["it", "italy", "italia"]},
    "india": {"code": "in", "name": "India", "aliases": ["in", "india", "ind"]},
    "netherlands": {"code": "nl", "name": "Netherlands", "aliases": ["nl", "netherlands", "holland"]},
    "switzerland": {"code": "ch", "name": "Switzerland", "aliases": ["ch", "switzerland"]},
    "sweden": {"code": "se", "name": "Sweden", "aliases": ["se", "sweden"]},
    "ukraine": {"code": "ua", "name": "Ukraine", "aliases": ["ua", "ukraine"]},
    "japan": {"code": "jp", "name": "Japan", "aliases": ["jp", "japan"]},
    "china": {"code": "cn", "name": "China", "aliases": ["cn", "china"]}
}

def resolve_country(location: str) -> Optional[Dict[str, Any]]:
    if not location:
        return None
    loc_clean = location.strip().lower()
    for main_key, data in COUNTRY_MAPPING.items():
        if loc_clean == main_key:
            return data
        for alias in data["aliases"]:
            if loc_clean == alias or alias in loc_clean:
                return data
    return None

def generate_name_permutations(name: str, country_code: str = "") -> List[str]:
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', name.strip().lower())
    parts = clean.split()
    if not parts:
        return []
    
    variants = []
    if len(parts) == 1:
        base = parts[0]
        variants.extend([base])
        if country_code:
            variants.extend([f"{base}_{country_code}", f"{base}.{country_code}"])
        return variants

    first, last = parts[0], parts[-1]
    variants.extend([
        f"{first}_{last}",
        f"{first}.{last}",
        f"{first}{last}",
        f"{first[0]}_{last}",
        f"{first[0]}.{last}",
        f"{first[0]}{last}",
        f"{last}_{first}",
        f"{last}.{first}",
        f"{first}_{last[0]}"
    ])

    if country_code:
        variants.extend([
            f"{first}_{last}_{country_code}",
            f"{first}.{last}.{country_code}",
            f"{first}{last}_{country_code}"
        ])

    return list(dict.fromkeys(variants))

def _digit_collision_variants(seed: str) -> List[str]:
    """Generate digit-collision variants of a seed handle.

    Techniques:
    1. For seeds ending in digits: zero-padding (user7 -> user07, user007),
       removing leading zeros (user07 -> user7), digit block reversal (user12 -> user21),
       adjacent number offsets (user1 -> user2), and 2-digit <-> 4-digit year expansion (user24 <-> user2024).
    2. For seeds without digits: standard numeric collision anchors (user1, user01, user123).
    """
    variants = []
    m = re.search(r'(\d+)$', seed)
    if m:
        num = m.group(1)
        base = seed[:m.start()]
        # Zero padding
        for extra in (1, 2):
            variants.append(f"{base}{'0' * extra}{num}")
        # Strip leading zeros
        if num.startswith('0') and num.strip('0'):
            variants.append(f"{base}{num.lstrip('0')}")
        # Reverse digit block
        if len(num) > 1 and num != num[::-1]:
            variants.append(f"{base}{num[::-1]}")
        # 2-digit to 4-digit year expansion
        if len(num) == 2:
            val = int(num)
            if val <= 30:
                variants.append(f"{base}20{num}")
            elif val >= 50:
                variants.append(f"{base}19{num}")
        elif len(num) == 4 and (num.startswith('19') or num.startswith('20')):
            variants.append(f"{base}{num[2:]}")
        # Adjacent offset
        try:
            val = int(num)
            if 0 <= val <= 99:
                variants.append(f"{base}{val + 1}")
                if val > 0:
                    variants.append(f"{base}{val - 1}")
        except ValueError:
            pass
    else:
        for sfx in ["1", "01", "123", "0", "2"]:
            variants.append(f"{seed}{sfx}")
            variants.append(f"{seed}_{sfx}")

    return list(dict.fromkeys(variants))


def generate_permutations(
    seed_username: str,
    known_names: List[str] = None,
    location: str = "",
    enable_digit_collisions: bool = False
) -> List[Dict[str, Any]]:
    results = []
    seen = set()

    country_info = resolve_country(location)
    country_code = country_info["code"] if country_info else ""

    # 1. Exact Seed Identifier
    if seed_username:
        clean_seed = seed_username.strip().lstrip('@').rstrip('/').lower()
        seen.add(clean_seed)
        results.append({
            "username": clean_seed,
            "category": "Exact Match",
            "rule": "Seed identifier",
            "similarity": 100,
            "is_seed": True
        })

        # Delimiter swaps (_ vs . vs none)
        for delim in ["_", ".", "-"]:
            if delim in clean_seed:
                for target_delim in ["_", ".", ""]:
                    if target_delim != delim:
                        p = clean_seed.replace(delim, target_delim)
                        if p and p not in seen:
                            seen.add(p)
                            results.append({
                                "username": p,
                                "category": "Delimiter Swap",
                                "rule": f"Delimiter swap ({delim} -> {target_delim or 'none'})",
                                "similarity": 95,
                                "is_seed": False
                            })

        # Suffix variations for country
        if country_code:
            for cv in [f"{clean_seed}_{country_code}", f"{clean_seed}.{country_code}"]:
                if cv not in seen:
                    seen.add(cv)
                    results.append({
                        "username": cv,
                        "category": "Country Context",
                        "rule": f"Appended country suffix '_{country_code}'",
                        "similarity": 90,
                        "is_seed": False
                    })

        # Digit-collision variants (zero-padding / digit reversal on numeric suffixes)
        if enable_digit_collisions:
            for dc in _digit_collision_variants(clean_seed):
                if dc not in seen:
                    seen.add(dc)
                    results.append({
                        "username": dc,
                        "category": "Digit Collision",
                        "rule": "Digit collision variant",
                        "similarity": 85,
                        "is_seed": False
                    })

    # 2. Known Names Handling
    if known_names:
        for name in known_names:
            name_perms = generate_name_permutations(name, country_code=country_code)
            for i, np in enumerate(name_perms):
                if np not in seen:
                    seen.add(np)
                    results.append({
                        "username": np,
                        "category": "Name Construction",
                        "rule": f"Constructed handle from name '{name}'",
                        "similarity": 95 if i == 0 and not seed_username else 88,
                        "is_seed": (i == 0 and not seed_username)
                    })

    return results