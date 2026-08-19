import re
from typing import List, Dict, Any, Optional

COUNTRY_MAPPING: Dict[str, Dict[str, Any]] = {
    "israel": {"code": "il", "name": "Israel", "aliases": ["israel", "il", "ישראל", "telaviv", "jerusalem"]},
    "united states": {"code": "us", "name": "United States", "aliases": ["usa", "us", "united states", "america", "united states of america"]},
    "united kingdom": {"code": "uk", "name": "United Kingdom", "aliases": ["uk", "united kingdom", "britain", "england", "gb", "great britain"]},
    "new zealand": {"code": "nz", "name": "New Zealand", "aliases": ["nz", "new zealand", "new zealend", "newzealand", "kiwi", "aotearoa"]},
    "australia": {"code": "au", "name": "Australia", "aliases": ["au", "australia", "aus", "oz"]},
    "canada": {"code": "ca", "name": "Canada", "aliases": ["ca", "canada", "can"]},
    "germany": {"code": "de", "name": "Germany", "aliases": ["de", "germany", "deutschland", "ger"]},
    "france": {"code": "fr", "name": "France", "aliases": ["fr", "france", "fra"]},
    "russia": {"code": "ru", "name": "Russia", "aliases": ["ru", "russia", "rf", "rossiya"]},
    "brazil": {"code": "br", "name": "Brazil", "aliases": ["br", "brazil", "brasil"]},
    "spain": {"code": "es", "name": "Spain", "aliases": ["es", "spain", "espana"]},
    "italy": {"code": "it", "name": "Italy", "aliases": ["it", "italy", "italia"]},
    "india": {"code": "in", "name": "India", "aliases": ["in", "india", "ind", "bharat"]},
    "netherlands": {"code": "nl", "name": "Netherlands", "aliases": ["nl", "netherlands", "holland"]},
    "switzerland": {"code": "ch", "name": "Switzerland", "aliases": ["ch", "switzerland", "swiss"]},
    "sweden": {"code": "se", "name": "Sweden", "aliases": ["se", "sweden", "sverige"]},
    "ukraine": {"code": "ua", "name": "Ukraine", "aliases": ["ua", "ukraine", "ukraina"]},
    "japan": {"code": "jp", "name": "Japan", "aliases": ["jp", "japan", "nihon", "nippon"]},
    "china": {"code": "cn", "name": "China", "aliases": ["cn", "china", "prc"]}
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
        variants.extend([base, f"{base}1", f"{base}2", f"{base}3"])
        if country_code:
            variants.extend([f"{base}_{country_code}", f"{base}.{country_code}", f"{country_code}_{base}"])
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
        f"{last}{first}",
        f"{first}_{last[0]}",
        f"{first}.{last[0]}"
    ])

    if country_code:
        variants.extend([
            f"{first}_{last}_{country_code}",
            f"{first}.{last}.{country_code}",
            f"{first}{last}_{country_code}",
            f"{first}_{last[0]}_{country_code}"
        ])

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

    # 1. If seed username exists, add exact seed
    if seed_username:
        clean_seed = seed_username.strip().lower()
        seen.add(clean_seed)
        results.append({
            "username": clean_seed,
            "category": "Exact Match",
            "rule": "Seed identifier",
            "similarity": 100
        })

        # Delimiter permutations (_ vs . vs -)
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
                                "rule": f"Replaced '{delim}' with '{target_delim or 'none'}'",
                                "similarity": 93
                            })

        # Country code variations
        if country_code:
            country_variants = [
                f"{clean_seed}_{country_code}",
                f"{clean_seed}.{country_code}",
                f"{country_code}_{clean_seed}"
            ]
            for cv in country_variants:
                if cv not in seen:
                    seen.add(cv)
                    results.append({
                        "username": cv,
                        "category": "Country Context",
                        "rule": f"Appended country code '{country_code}' ({country_info['name']})",
                        "similarity": 90
                    })

        # Digit collisions
        if enable_digit_collisions:
            for digit in ["1", "2", "3", "7", "9", "01", "123"]:
                pv = f"{clean_seed}{digit}"
                if pv not in seen:
                    seen.add(pv)
                    results.append({
                        "username": pv,
                        "category": "Digit Collision",
                        "rule": f"Appended digit suffix '{digit}'",
                        "similarity": 94
                    })

    # 2. Known names handling
    if known_names:
        for name in known_names:
            name_perms = generate_name_permutations(name, country_code=country_code)
            for np in name_perms:
                if np not in seen:
                    seen.add(np)
                    results.append({
                        "username": np,
                        "category": "Name Construction",
                        "rule": f"Constructed handle from name '{name}'",
                        "similarity": 88
                    })

    return results