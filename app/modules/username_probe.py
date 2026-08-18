import asyncio
import httpx
from typing import List, Dict, Any, Optional
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, MAX_CONCURRENT_REQUESTS

# High-signal platform probe database across 8 essential categories
SITES_DB = [
    # ── Dev & Code ──────────────────────────────
    {"name": "GitHub", "url": "https://github.com/{}", "check": "status_code", "category": "Developer"},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "check": "status_code", "category": "Developer"},
    {"name": "DockerHub", "url": "https://hub.docker.com/u/{}", "check": "status_code", "category": "Developer"},
    {"name": "PyPI", "url": "https://pypi.org/user/{}/", "check": "status_code", "category": "Developer"},
    {"name": "NPM", "url": "https://www.npmjs.com/~{}", "check": "status_code", "category": "Developer"},
    {"name": "Replit", "url": "https://replit.com/@{}", "check": "status_code", "category": "Developer"},
    {"name": "CodePen", "url": "https://codepen.io/{}", "check": "status_code", "category": "Developer"},
    {"name": "HackerRank", "url": "https://www.hackerrank.com/{}", "check": "status_code", "category": "Developer"},
    {"name": "LeetCode", "url": "https://leetcode.com/{}/", "check": "status_code", "category": "Developer"},
    {"name": "Kaggle", "url": "https://www.kaggle.com/{}", "check": "status_code", "category": "Developer"},

    # ── Social & Community ───────────────────────
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}/about.json", "check": "reddit_json", "profile_url": "https://reddit.com/user/{}", "category": "Social"},
    {"name": "Twitter / X", "url": "https://twitter.com/{}", "check": "status_code", "category": "Social"},
    {"name": "Instagram", "url": "https://www.instagram.com/{}/", "check": "status_code", "category": "Social"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}/", "check": "status_code", "category": "Social"},
    {"name": "Threads", "url": "https://www.threads.net/@{}", "check": "status_code", "category": "Social"},
    {"name": "Mastodon", "url": "https://mastodon.social/@{}", "check": "status_code", "category": "Social"},
    {"name": "Bluesky", "url": "https://bsky.app/profile/{}.bsky.social", "check": "status_code", "category": "Social"},
    {"name": "Telegram", "url": "https://t.me/{}", "check": "telegram_html", "category": "Social"},
    {"name": "Medium", "url": "https://medium.com/@{}", "check": "status_code", "category": "Social"},
    {"name": "Dev.to", "url": "https://dev.to/{}", "check": "status_code", "category": "Social"},
    {"name": "Substack", "url": "https://{}.substack.com", "check": "status_code", "category": "Social"},

    # ── Media, Video & Audio ─────────────────────
    {"name": "YouTube", "url": "https://www.youtube.com/@{}", "check": "status_code", "category": "Media"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "check": "status_code", "category": "Media"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "check": "status_code", "category": "Media"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "check": "status_code", "category": "Media"},
    {"name": "Bandcamp", "url": "https://{}.bandcamp.com", "check": "status_code", "category": "Media"},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "check": "status_code", "category": "Media"},
    {"name": "DailyMotion", "url": "https://www.dailymotion.com/{}", "check": "status_code", "category": "Media"},

    # ── Gaming ───────────────────────────────────
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "check": "steam_html", "category": "Gaming"},
    {"name": "Chess.com", "url": "https://www.chess.com/member/{}", "check": "status_code", "category": "Gaming"},
    {"name": "Lichess", "url": "https://lichess.org/@/{}", "check": "status_code", "category": "Gaming"},
    {"name": "Roblox", "url": "https://www.roblox.com/user.aspx?username={}", "check": "status_code", "category": "Gaming"},
    {"name": "Speedrun.com", "url": "https://www.speedrun.com/user/{}", "check": "status_code", "category": "Gaming"},

    # ── Design & Creative ────────────────────────
    {"name": "Behance", "url": "https://www.behance.net/{}", "check": "status_code", "category": "Design"},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "check": "status_code", "category": "Design"},
    {"name": "ArtStation", "url": "https://www.artstation.com/{}", "check": "status_code", "category": "Design"},
    {"name": "Flickr", "url": "https://www.flickr.com/people/{}", "check": "status_code", "category": "Design"},
    {"name": "500px", "url": "https://500px.com/p/{}", "check": "status_code", "category": "Design"},

    # ── Crypto, Web3 & Tech ──────────────────────
    {"name": "Keybase", "url": "https://keybase.io/{}", "check": "status_code", "category": "Tech"},
    {"name": "ProductHunt", "url": "https://www.producthunt.com/@{}", "check": "status_code", "category": "Tech"},
    {"name": "Discourse", "url": "https://meta.discourse.org/u/{}", "check": "status_code", "category": "Forums"},
    {"name": "About.me", "url": "https://about.me/{}", "check": "status_code", "category": "Personal"},
    {"name": "Linktree", "url": "https://linktr.ee/{}", "check": "status_code", "category": "Personal"},
]

async def probe_single_target(client: httpx.AsyncClient, site: Dict[str, Any], username: str) -> Dict[str, Any]:
    """Probe a single website for a username with response analysis."""
    url = site["url"].format(username)
    profile_url = site.get("profile_url", url).format(username)
    site_name = site["name"]
    category = site["category"]
    check_type = site.get("check", "status_code")

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
        resp = await client.get(url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        t1 = asyncio.get_event_loop().time()
        latency = int((t1 - t0) * 1000)
        result["status_code"] = resp.status_code
        result["latency_ms"] = latency

        if check_type == "status_code":
            if resp.status_code == 200:
                # Extra check: ensure not a generic 200 soft-404 page
                text_lower = resp.text.lower()
                if "page not found" not in text_lower and "user not found" not in text_lower and "doesn't exist" not in text_lower:
                    result["found"] = True

        elif check_type == "reddit_json":
            if resp.status_code == 200 and "data" in resp.text:
                result["found"] = True

        elif check_type == "telegram_html":
            if resp.status_code == 200:
                # Telegram shows "tgme_page_extra" or preview info if account exists
                if "extra-class" in resp.text or "tgme_page_title" in resp.text or "Preview channel" in resp.text:
                    if "If you have Telegram, you can contact" in resp.text:
                        result["found"] = True

        elif check_type == "steam_html":
            if resp.status_code == 200 and "The specified profile could not be found" not in resp.text:
                result["found"] = True

    except httpx.TimeoutException:
        result["error"] = "TIMEOUT"
    except httpx.RequestError as e:
        result["error"] = "NETWORK_ERROR"
    except Exception as e:
        result["error"] = str(e)

    return result

async def scan_usernames_async(usernames: List[str], concurrency: int = MAX_CONCURRENT_REQUESTS):
    """
    Scans a list of usernames against all sites database with throttled semaphore.
    Yields results as each probe completes.
    """
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