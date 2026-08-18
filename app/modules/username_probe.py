import asyncio
import json
import httpx
from typing import List, Dict, Any, Optional
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS

SITES_DB = [
    # ── Social & Community Platforms ──
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{}/",
        "profile_url": "https://www.instagram.com/{}/",
        "check": "instagram_strict",
        "category": "Social"
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{}/",
        "profile_url": "https://www.pinterest.com/{}/",
        "check": "pinterest_strict",
        "category": "Social"
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{}",
        "profile_url": "https://www.tiktok.com/@{}",
        "check": "oembed_strict",
        "category": "Social"
    },
    {
        "name": "Twitter / X",
        "url": "https://publish.twitter.com/oembed?url=https://twitter.com/{}",
        "profile_url": "https://twitter.com/{}",
        "check": "oembed_strict",
        "category": "Social"
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{}",
        "profile_url": "https://www.youtube.com/@{}",
        "check": "youtube_strict",
        "category": "Social"
    },
    {
        "name": "Reddit",
        "url": "https://old.reddit.com/user/{}/",
        "profile_url": "https://reddit.com/user/{}",
        "check": "reddit_strict",
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
        "name": "Mastodon",
        "url": "https://mastodon.social/api/v1/accounts/lookup?acct={}",
        "profile_url": "https://mastodon.social/@{}",
        "check": "json_key",
        "key": "username",
        "category": "Social"
    },

    # ── Developer & Engineering Platforms ──
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

    # ── Gaming Platforms ──
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
        "category": "Media"
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
        "category": "Media"
    }
]

async def probe_single_target(client: httpx.AsyncClient, site: Dict[str, Any], username: str) -> Dict[str, Any]:
    url_template = site["url"]
    count_fmt = url_template.count("{}")
    url = url_template.format(*([username] * count_fmt))
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

        if check_type == "instagram_strict":
            headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"

        elif check_type in ["pinterest_strict", "youtube_strict", "reddit_strict"]:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

        resp = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        t1 = asyncio.get_event_loop().time()
        result["status_code"] = resp.status_code
        result["latency_ms"] = int((t1 - t0) * 1000)

        # 1. Instagram Strict Inspection
        if check_type == "instagram_strict":
            if resp.status_code == 200:
                txt = resp.text.lower()
                if f"@{username.lower()}" in txt or "instagram photos and videos" in txt:
                    if "accounts/login" not in resp.url.path:
                        result["found"] = True

        # 2. Pinterest Strict Inspection
        elif check_type == "pinterest_strict":
            if resp.status_code == 200:
                txt = resp.text
                if ("__PWS_DATA__" in txt or "on Pinterest" in txt) and "User not found" not in txt and "could not be found" not in txt:
                    result["found"] = True

        # 3. YouTube Channel Inspection
        elif check_type == "youtube_strict":
            if resp.status_code == 200:
                txt = resp.text
                if ("channel" in txt.lower() or "subscriber" in txt.lower() or "og:title" in txt) and "404 Not Found" not in txt and "This page isn't available" not in txt:
                    result["found"] = True

        # 4. Reddit Strict Inspection
        elif check_type == "reddit_strict":
            if resp.status_code == 200:
                txt = resp.text.lower()
                if f"/user/{username.lower()}" in txt and "nobody on reddit goes by that name" not in txt and "page not found" not in txt:
                    result["found"] = True

        # 5. TikTok / Twitter oEmbed Verification
        elif check_type == "oembed_strict":
            if resp.status_code == 200:
                data = resp.json()
                if data.get("author_name") or data.get("title") or data.get("html"):
                    result["found"] = True

        # 6. JSON Key Existence
        elif check_type == "json_key":
            if resp.status_code == 200:
                data = resp.json()
                req_key = site.get("key")
                if req_key and req_key in data and data[req_key]:
                    result["found"] = True

        # 7. JSON Array Non-Empty
        elif check_type == "json_array_nonempty":
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    result["found"] = True

        # 8. Telegram Verification
        elif check_type == "telegram_verified":
            if resp.status_code == 200:
                text = resp.text
                if "tgme_page_title" in text and "tgme_page_extra" in text:
                    if "If you have Telegram, you can contact" in text or f"@{username.lower()}" in text.lower():
                        result["found"] = True

        # 9. Keybase API
        elif check_type == "keybase_json":
            if resp.status_code == 200:
                data = resp.json()
                them = data.get("them", [])
                if them and them[0] is not None:
                    result["found"] = True

        # 10. Steam XML Profile
        elif check_type == "steam_xml":
            if resp.status_code == 200 and "<steamID64>" in resp.text and "<error>" not in resp.text:
                result["found"] = True

        # 11. PyPI Profile
        elif check_type == "pypi_profile":
            if resp.status_code == 200 and "User profile of" in resp.text:
                result["found"] = True

        # 12. SoundCloud Strict
        elif check_type == "soundcloud_strict":
            if resp.status_code == 200 and 'content="soundcloud://users:' in resp.text:
                result["found"] = True

        # 13. Bandcamp Strict
        elif check_type == "bandcamp_strict":
            if resp.status_code == 200 and "bandcamp.com" in resp.text:
                txt = resp.text.lower()
                if "domain not found" not in txt and "sign up" not in txt and "create your account" not in txt:
                    result["found"] = True

        # 14. Behance Strict
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