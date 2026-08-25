import asyncio
import hashlib
import re
import httpx
from typing import Dict, Any
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, HTTP_VERIFY

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

# Fallback heuristic used only when dnspython is unavailable (keeps the app
# functional on bare installs that do not run `pip install dnspython`).
COMMON_MAIL_PROVIDERS = {
    "gmail.com": "Google Workspace (Gmail)",
    "googlemail.com": "Google Workspace (Gmail)",
    "yahoo.com": "Yahoo Mail",
    "yahoo.co.uk": "Yahoo Mail",
    "outlook.com": "Microsoft Outlook",
    "hotmail.com": "Microsoft Outlook",
    "live.com": "Microsoft Outlook",
    "msn.com": "Microsoft Outlook",
    "aol.com": "AOL",
    "icloud.com": "Apple iCloud Mail",
    "me.com": "Apple iCloud Mail",
    "protonmail.com": "ProtonMail",
    "proton.me": "ProtonMail",
    "mail.com": "Mail.com",
    "zoho.com": "Zoho Mail",
    "yandex.com": "Yandex Mail",
    "gmx.com": "GMX Mail",
    "gmx.net": "GMX Mail",
    "qq.com": "Tencent QQ Mail",
    "163.com": "NetEase 163 Mail",
}


def resolve_mx_provider(domain: str):
    """Return (mx_provider, deliverable) for a domain.

    Uses dnspython when available (true DNS MX lookup), with explicit public
    resolvers (Cloudflare 1.1.1.1 + Google 8.8.8.8) so it works correctly on
    Android where /etc/resolv.conf does not exist. Falls back to a
    known-provider heuristic when DNS is unavailable or times out.
    `deliverable` is True/False when a real answer exists, None when unknown.
    """
    try:
        import dns.resolver

        # Build a resolver with public nameservers so this works on Android
        # (which has no /etc/resolv.conf) and on devices behind captive portals.
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ['1.1.1.1', '8.8.8.8', '8.8.4.4']
        resolver.lifetime = 5.0
        resolver.timeout  = 3.0

        answers = resolver.resolve(domain, "MX")
        mxs = sorted(answers, key=lambda r: r.preference)
        if mxs:
            host = str(mxs[0].exchange).rstrip(".")
            return host, True
        return "No MX records", False
    except Exception:
        pass

    base = domain.lower()
    if base in COMMON_MAIL_PROVIDERS:
        return COMMON_MAIL_PROVIDERS[base], True
    if base.endswith(".protonmail.com") or "protonmail" in base:
        return "ProtonMail", True
    return "Unknown (DNS lookup unavailable)", None


async def probe_email_intelligence(email: str) -> Dict[str, Any]:
    """Validates email format, checks MX/deliverability, Gravatar avatar & GitHub footprint."""
    clean_email = email.strip().lower()
    is_valid_format = bool(re.match(EMAIL_REGEX, clean_email))

    if not is_valid_format:
        return {
            "email": email,
            "valid_syntax": False,
            "error": "Invalid email syntax format"
        }

    domain = clean_email.split("@")[1]
    user_part = clean_email.split("@")[0]

    # Gravatar MD5 hash calculation
    email_hash = hashlib.md5(clean_email.encode('utf-8')).hexdigest()
    gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    gravatar_profile = f"https://en.gravatar.com/{email_hash}.json"

    mx_provider, deliverable = resolve_mx_provider(domain)

    result = {
        "email": clean_email,
        "valid_syntax": True,
        "user_part": user_part,
        "domain": domain,
        "mx_provider": mx_provider,
        "deliverable": deliverable,
        "gravatar": {
            "exists": False,
            "avatar_url": None,
            "display_name": None,
            "profile_url": None
        },
        "footprints": []
    }
    if mx_provider and mx_provider not in ("No MX records", "Unknown (DNS lookup unavailable)"):
        result["footprints"].append(f"Mail exchange active ({mx_provider})")

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, verify=HTTP_VERIFY) as client:
        # 1. Check Gravatar Profile
        try:
            attempts = 2
            backoff = 0.1
            resp = None
            for _ in range(attempts):
                try:
                    resp = await client.get(gravatar_profile, headers=COMMON_HEADERS)
                except (httpx.TimeoutException, httpx.RequestError):
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                break

            if resp and resp.status_code == 200:
                data = resp.json()
                entry = data.get("entry", [{}])[0]
                result["gravatar"]["exists"] = True
                result["gravatar"]["avatar_url"] = f"https://www.gravatar.com/avatar/{email_hash}?s=200"
                result["gravatar"]["display_name"] = entry.get("displayName")
                result["gravatar"]["profile_url"] = entry.get("profileUrl")
                result["footprints"].append("Gravatar Profile Found")
        except Exception:
            pass

        # 2. Check GitHub Public Commits / Search
        try:
            gh_url = f"https://api.github.com/search/users?q={clean_email}+in:email"
            attempts = 2
            backoff = 0.1
            gh_resp = None
            for _ in range(attempts):
                try:
                    gh_resp = await client.get(gh_url, headers=COMMON_HEADERS)
                except (httpx.TimeoutException, httpx.RequestError):
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                break
            if gh_resp and gh_resp.status_code == 200:
                gh_data = gh_resp.json()
                if gh_data.get("total_count", 0) > 0:
                    gh_user = gh_data["items"][0]
                    result["footprints"].append(f"Linked GitHub Account (@{gh_user.get('login')})")
        except Exception:
            pass

    return result