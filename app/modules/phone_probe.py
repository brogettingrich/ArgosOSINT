import re
from typing import Dict, Any

try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

FALLBACK_COUNTRY_CODES = {
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
    "+31": {"country": "Netherlands", "iso": "NL"},
    "+41": {"country": "Switzerland", "iso": "CH"},
    "+46": {"country": "Sweden", "iso": "SE"},
    "+380": {"country": "Ukraine", "iso": "UA"}
}

def analyze_phone_number(raw: str) -> Dict[str, Any]:
    digits_only = re.sub(r'\D', '', raw)
    if not digits_only or len(digits_only) < 7:
        return {
            "raw": raw,
            "valid": False,
            "error": "Phone number contains too few digits"
        }

    raw_clean = raw.strip()
    if not raw_clean.startswith('+'):
        raw_clean = f"+{digits_only}"

    if HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(raw_clean, None)
            is_valid = phonenumbers.is_valid_number(parsed) or phonenumbers.is_possible_number(parsed)
            
            region_code = phonenumbers.region_code_for_number(parsed) or "UNKNOWN"
            geo_desc = geocoder.description_for_number(parsed, "en") or region_code
            car_desc = carrier.name_for_number(parsed, "en") or ""
            tz_list = list(timezone.time_zones_for_number(parsed)) if parsed else []

            e164_str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            intl_str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            nat_str = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)

            return {
                "raw": raw,
                "valid": is_valid,
                "e164": e164_str,
                "intl_format": intl_str,
                "national_format": nat_str,
                "country": geo_desc,
                "iso": region_code,
                "carrier": car_desc,
                "timezones": tz_list,
                "country_code": str(parsed.country_code),
                "national_number": str(parsed.national_number)
            }
        except Exception:
            pass

    # Fallback parser if phonenumbers fails
    e164 = f"+{digits_only}"
    detected_country = "International / Unknown"
    iso_code = "UNKNOWN"
    cc_length = 1

    for code, meta in sorted(FALLBACK_COUNTRY_CODES.items(), key=lambda x: -len(x[0])):
        if e164.startswith(code):
            detected_country = meta["country"]
            iso_code = meta["iso"]
            cc_length = len(code)
            break

    cc_part = e164[:cc_length]
    national_part = digits_only[cc_length - 1:]

    return {
        "raw": raw,
        "valid": True,
        "e164": e164,
        "intl_format": f"{cc_part} {national_part}",
        "national_format": national_part,
        "country": detected_country,
        "iso": iso_code,
        "carrier": "",
        "timezones": [],
        "country_code": cc_part.lstrip('+'),
        "national_number": national_part
    }