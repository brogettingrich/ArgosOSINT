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
    "+64": {"country": "New Zealand", "iso": "NZ"},
    "+20": {"country": "Egypt", "iso": "EG"},
    "+27": {"country": "South Africa", "iso": "ZA"},
    "+31": {"country": "Netherlands", "iso": "NL"},
    "+41": {"country": "Switzerland", "iso": "CH"},
    "+46": {"country": "Sweden", "iso": "SE"},
    "+380": {"country": "Ukraine", "iso": "UA"},
}


def _group_local(digits: str) -> str:
    """Group a national number into readable chunks (right-to-left by 3)."""
    chunks = []
    while len(digits) > 3:
        chunks.insert(0, digits[-3:])
        digits = digits[:-3]
    chunks.insert(0, digits)
    return " ".join(chunks)


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

    e164 = f"+{digits_only}"

    detected_country = "International / Unknown"
    iso_code = "UNKNOWN"
    cc_length = None
    for code, meta in sorted(COUNTRY_CODES.items(), key=lambda x: -len(x[0])):
        if e164.startswith(code):
            detected_country = meta["country"]
            iso_code = meta["iso"]
            cc_length = len(code) - 1  # digits in the country code
            break

    national = digits_only[cc_length:] if cc_length else digits_only

    intl_format = e164
    if cc_length and len(national) == 10:
        intl_format = f"{e164[:cc_length + 1]} {national[:3]} {national[3:6]} {national[6:]}"
    elif cc_length and national:
        intl_format = f"{e164[:cc_length + 1]} {_group_local(national)}"

    local_format = ""
    if cc_length and len(national) == 10 and e164.startswith("+1"):
        local_format = f"({national[:3]}) {national[3:6]}-{national[6:]}"
    elif national:
        local_format = _group_local(national)

    variations = [e164, digits_only, intl_format]
    wa_me = f"https://wa.me/{digits_only}"

    return {
        "raw": raw,
        "valid": True,
        "e164": e164,
        "intl_format": intl_format,
        "local_format": local_format,
        "digits_only": digits_only,
        "country": detected_country,
        "iso": iso_code,
        "wa_me": wa_me,
        "dork_variations": list(dict.fromkeys(variations)),
        "lookup_dorks": [
            f'"{e164}"',
            f'"{digits_only}"',
            f'site:whatsapp.com "{digits_only}"',
            f'site:telegram.me "{digits_only}"'
        ]
    }