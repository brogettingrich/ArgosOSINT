import hashlib
import re
import httpx
from typing import Dict, Any, List
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, HTTP_VERIFY

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

async def probe_email_intelligence(email: str) -> Dict[str, Any]:
    """
    Validates email format, extracts domain, checks Gravatar avatar & GitHub footprint.
    """
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

    result = {
        "email": clean_email,
        "valid_syntax": True,
        "user_part": user_part,
        "domain": domain,
        "gravatar": {
            "exists": False,
            "avatar_url": None,
            "display_name": None,
            "profile_url": None
        },
        "footprints": []
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, verify=HTTP_VERIFY) as client:
        # 1. Check Gravatar Profile
        try:
            # Retry loop for transient errors
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