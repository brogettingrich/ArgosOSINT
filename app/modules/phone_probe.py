import re
from typing import Dict, Any

# Common Country Dialing Codes Table
COUNTRY_CODES = {
    "+1": {"country": "United States / Canada", "iso": "US/CA"},
    "+44": {"country": "United Kingdom", "iso": "GB"},
    "+49": {"country": "Germany", "iso": "DE"},
    "+33": {"country": "France", "iso": "FR"},
    "+34": {"country": "Spain", "iso": "ES"},
    "+39": {"country": "Italy", "iso": "IT"},
    "+7": {"country": "Russia / Kazakhstan", "iso": "RU/KZ"},
    "+81": {"country": "Japan", "iso": "JP"},
    "+82": {"country": "South Korea", "iso": "KR"},
    "+86": {"country": "China", "iso": "CN"},
    "+91": {"country": "India", "iso": "IN"},
    "+972": {"country": "Israel", "iso": "IL"},
    "+971": {"country": "United Arab Emirates", "iso": "AE"},
    "+966": {"country": "Saudi Arabia", "iso": "SA"},
    "+55": {"country": "Brazil", "iso": "BR"},
    "+52": {"country": "Mexico", "iso": "MX"},
    "+61": {"country": "Australia", "iso": "AU"},
    "+20": {"country": "Egypt", "iso": "EG"},
    "+27": {"country": "South Africa", "iso": "ZA"},
}

def analyze_phone_number(raw: str) -> Dict[str, Any]:
    """
    Parses and standardizes phone number formats and maps international country codes.
    """
    digits_only = re.sub(r'\D', '', raw)
    if not digits_only or len(digits_only) < 7:
        return {
            "raw": raw,
            "valid": False,
            "error": "Phone number contains too few digits"
        }

    formatted_plus = f"+{digits_only}" if not raw.startswith("+") else raw
    detected_country = "International / Unknown"
    iso_code = "UNKNOWN"

    for code, meta in sorted(COUNTRY_CODES.items(), key=lambda x: -len(x[0])):
        if formatted_plus.startswith(code):
            detected_country = meta["country"]
            iso_code = meta["iso"]
            break

    # Variations for web search dorking
    variations = [
        formatted_plus,
        digits_only,
        f"+{digits_only[:3]} {digits_only[3:6]} {digits_only[6:]}" if len(digits_only) >= 9 else formatted_plus
    ]

    return {
        "raw": raw,
        "valid": True,
        "e164": formatted_plus,
        "digits_only": digits_only,
        "country": detected_country,
        "iso": iso_code,
        "dork_variations": list(set(variations)),
        "lookup_dorks": [
            f'"{formatted_plus}"',
            f'"{digits_only}"',
            f'site:whatsapp.com "{digits_only}"',
            f'site:telegram.me "{digits_only}"'
        ]
    }