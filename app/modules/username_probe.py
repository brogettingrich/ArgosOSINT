import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS

SITES_DB = [
    # ── Verified Developer & Tech Platforms (Zero False Positives) ──
    {
        "name": "GitHub",
        "url": "https://api.github.com/users/{}",
        "profile_url": "https://github.com/{}",
        "check": "json_key",
        "key": "login",
        "category": "Developer"
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/api/v4/users?username={}",
        "profile_url": "https://gitlab.com/{}",
        "check": "json_array_nonempty",
        "category": "Developer"
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/v2/users/{}/",
        "profile_url": "https://hub.docker.com/u/{}",
        "check": "json_key",
        "key": "username",
        "category": "Developer"
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{}/",
        "profile_url": "https://pypi.org/user/{}/",
        "check": "pypi_profile",
        "category": "Developer"
    },
    {
        "name": "HackerRank",
        "url": "https://www.hackerrank.com/rest/hackers/{}",
        "profile_url": "https://www.hackerrank.com/{}",
        "check": "json_key",
        "key": "model",
        "category": "Developer"
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/api/users/by_username?url={}",
        "profile_url": "https://dev.to/{}",
        "check": "json_key",
        "key": "username",
        "category": "Developer"
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/_/api/1.0/user/lookup.json?usernames={}",
        "profile_url": "https://keybase.io/{}",
        "check": "keybase_json",
        "category": "Developer"
    },
    {
        "name": "Replit",
        "url": "https://replit.com/data/profiles/{}",
        "profile_url": "https://replit.com/@{}",
        "check": "json_key",
        "key": "username",
        "category": "Developer"
    },

    # ── Social & Messaging (Verified Public APIs / Signatures) ──
    {
        "name": "Twitter / X",
        "url": "https://publish.twitter.com/oembed?url=https://twitter.com/{}",
        "profile_url": "https://twitter.com/{}",
        "check": "oembed_200",
        "category": "Social"
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{}",
        "profile_url": "https://t.me/{}",
        "check": "telegram_verified",
        "category": "Social"
    },
    {
        "name": "Bluesky",
        "url": "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={}.bsky.social",
        "profile_url": "https://bsky.app/profile/{}.bsky.social",
        "check": "json_key",
        "key": "handle",
        "category": "Social"
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{}/about.json",
        "profile_url": "https://reddit.com/user/{}",
        "check": "reddit_json",
        "category": "Social"
    },
    {
        "name": "Mastodon",
        "url": "https://mastodon.social/api/v1/accounts/lookup?acct={}",
        "profile_url": "https://mastodon.social/@{}",
        "check": "json_key",
        "key": "username",
        "category": "Social"
    },

    # ── Gaming & Virtual Platforms ──
    {
        "name": "Chess.com",
        "url": "https://api.chess.com/pub/player/{}",
        "profile_url": "https://www.chess.com/member/{}",
        "check": "json_key",
        "key": "username",
        "category": "Gaming"
    },
    {
        "name": "Lichess",
        "url": "https://lichess.org/api/user/{}",
        "profile_url": "https://lichess.org/@/{}",
        "check": "json_key",
        "key": "id",
        "category": "Gaming"
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{}/?xml=1",
        "profile_url": "https://steamcommunity.com/id/{}",
        "check": "steam_xml",
        "category": "Gaming"
    },

    # ── Media & Creative Networks ──
    {
        "name": "ArtStation",
        "url": "https://www.artstation.com/users/{}.json",
        "profile_url": "https://www.artstation.com/{}",
        "check": "json_key",
        "key": "username",
        "category": "Creative"
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{}",
        "profile_url": "https://soundcloud.com/{}",
        "check": "soundcloud_strict",
        "category": "Media"
    },
    {
        "name": "Bandcamp",
        "url": "https://{}.bandcamp.com",
        "profile_url": "https://{}.bandcamp.com",
        "check": "bandcamp_strict",
        "category": "Media"
    },
    {
        "name": "Behance",
        "url": "https://www.behance.net/{}",
        "profile_url": "https://www.behance.net/{}",
        "check": "behance_strict",
        "category": "Creative"
    }
]

async def probe_single_target(client: httpx.AsyncClient, site: Dict[str, Any], username: str) -> Dict[str, Any]:
    url = site["url"].format(username)
    profile_url = site.get("profile_url", url).format(username)
    site_name = site["name"]
    category = site["category"]
    check_type = site.get("check", "json_key")

    result = {
        "site": site_name,
        "category": category,
        "username": username,
        "profile_url": profile_url,
        "found": False,
        "status_code": 0,
        "latency_ms": 0,
        "error": None
    }

    try:
        t0 = asyncio.get_event_loop().time()
        headers = dict(COMMON_HEADERS)
        if "reddit" in url:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArgosOSINT/2.0"

        resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        t1 = asyncio.get_event_loop().time()
        result["status_code"] = resp.status_code
        result["latency_ms"] = int((t1 - t0) * 1000)

        # 1. Direct JSON key check
        if check_type == "json_key":
            if resp.status_code == 200:
                data = resp.json()
                req_key = site.get("key")
                if req_key and req_key in data and data[req_key]:
                    result["found"] = True

        # 2. JSON array non-empty
        elif check_type == "json_array_nonempty":
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    result["found"] = True

        # 3. Twitter / X Official oEmbed Validation (100% verified, rejects non-existent / signup pages)
        elif check_type == "oembed_200":
            if resp.status_code == 200:
                data = resp.json()
                if data.get("author_name") or data.get("html"):
                    result["found"] = True

        # 4. Telegram Verified Account Signature
        elif check_type == "telegram_verified":
            if resp.status_code == 200:
                text = resp.text
                if "tgme_page_title" in text and "tgme_page_extra" in text:
                    # Account exists if contact button or handle is present
                    if "If you have Telegram, you can contact" in text or f"@{username.lower()}" in text.lower():
                        result["found"] = True

        # 5. Reddit API
        elif check_type == "reddit_json":
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and data["data"].get("name"):
                    result["found"] = True

        # 6. Keybase API
        elif check_type == "keybase_json":
            if resp.status_code == 200:
                data = resp.json()
                them = data.get("them", [])
                if them and them[0] is not None:
                    result["found"] = True

        # 7. Steam XML Profile
        elif check_type == "steam_xml":
            if resp.status_code == 200 and "<steamID64>" in resp.text and "<error>" not in resp.text:
                result["found"] = True

        # 8. PyPI Profile
        elif check_type == "pypi_profile":
            if resp.status_code == 200 and "User profile of" in resp.text:
                result["found"] = True

        # 9. SoundCloud Strict
        elif check_type == "soundcloud_strict":
            if resp.status_code == 200 and 'content="soundcloud://users:' in resp.text:
                result["found"] = True

        # 10. Bandcamp Strict (Rejects sign-up & domain parking pages)
        elif check_type == "bandcamp_strict":
            if resp.status_code == 200 and "bandcamp.com" in resp.text:
                txt = resp.text.lower()
                if "domain not found" not in txt and "sign up" not in txt and "create your account" not in txt:
                    result["found"] = True

        # 11. Behance Strict
        elif check_type == "behance_strict":
            if resp.status_code == 200 and "behance.net" in resp.text:
                txt = resp.text.lower()
                if "page not found" not in txt and "sign up" not in txt:
                    result["found"] = True

    except httpx.TimeoutException:
        result["error"] = "TIMEOUT"
    except httpx.RequestError:
        result["error"] = "NETWORK_ERROR"
    except Exception as e:
        result["error"] = str(e)

    return result

async def scan_usernames_async(usernames: List[str], concurrency: int = MAX_CONCURRENT_REQUESTS):
    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)

    async with httpx.AsyncClient(limits=limits, verify=False) as client:
        async def bounded_probe(site, u):
            async with semaphore:
                return await probe_single_target(client, site, u)

        tasks = []
        for u in usernames:
            for site in SITES_DB:
                tasks.append(bounded_probe(site, u))

        for future in asyncio.as_completed(tasks):
            res = await future
            yield res