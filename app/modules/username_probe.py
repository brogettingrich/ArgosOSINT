import asyncio
import re
import time
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from urllib.parse import urlparse
from app.config import MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT, COMMON_HEADERS, HTTP_VERIFY
from app.modules.sites_catalog import SITES_CATALOG
from app.core.permutations import resolve_country

SITES_DB = SITES_CATALOG

# Global & Domain Concurrency Semaphores
DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def get_domain_semaphore(url: str) -> asyncio.Semaphore:
    domain = urlparse(url).netloc
    if domain not in DOMAIN_SEMAPHORES:
        DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(3)
    return DOMAIN_SEMAPHORES[domain]

# Anti-Bot & False Positive Challenge Signatures
CHALLENGE_PATTERNS = [
    "checking your browser",
    "just a moment...",
    "cloudflare",
    "attention required",
    "challenge-platform",
    "cf-browser-verification",
    "sina visitor system",
    "user not found",
    "page not found",
    "account doesn't exist",
    "couldn't find this account",
    "sorry, this page isn't available"
]

def extract_html_metadata(html: str) -> Dict[str, Any]:
    meta = {
        "display_name": None,
        "bio": None,
        "avatar_url": None,
        "outbound_links": [],
        "mentioned_handles": [],
        "mentioned_emails": []
    }
    if not html or len(html) < 50:
        return meta

    # 1. og:title
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.I)
    if not title_match:
        title_match = re.search(r'<title>(.*?)</title>', html, re.I)
    if title_match:
        raw_t = title_match.group(1).split('|')[0].split('•')[0].split('-')[0].strip()
        if not any(c in raw_t.lower() for c in ["404", "not found", "login", "browser", "challenge"]):
            meta["display_name"] = raw_t

    # 2. og:description / Bio
    desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', html, re.I)
    if not desc_match:
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.I)
    if desc_match:
        bio_text = desc_match.group(1).strip()
        if not any(c in bio_text.lower() for c in ["404", "not found", "accept tips with 0-5%"]):
            meta["bio"] = bio_text
            meta["mentioned_handles"] = list(set(re.findall(r'@([a-zA-Z0-9._]{3,30})', bio_text)))
            meta["mentioned_emails"] = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio_text)))

    # 3. og:image / Avatar
    img_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html, re.I)
    if img_match:
        meta["avatar_url"] = img_match.group(1).strip()

    # 4. Outbound links
    outbound = re.findall(r'href=["\'](https?://(?:www\.)?(?:linktr\.ee|beacons\.ai|carrd\.co|github\.com|twitter\.com|x\.com|t\.me)/[a-zA-Z0-9._/-]+)["\']', html, re.I)
    meta["outbound_links"] = list(set(outbound))[:5]

    return meta

async def check_single_site(client: httpx.AsyncClient, site: Dict[str, Any], username: str) -> Dict[str, Any]:
    url = site["url_template"].format(username)
    profile_url = site.get("profile_url", site["url_template"]).format(username)
    special_handler = site.get("special_handler")

    start_time = time.time()
    result = {
        "site": site["name"],
        "category": site.get("category", "General"),
        "username": username,
        "profile_url": profile_url,
        "found": False,
        "status_code": 0,
        "latency_ms": 0,
        "metadata": {}
    }

    dom_sem = get_domain_semaphore(url)

    async with GLOBAL_SEMAPHORE:
        async with dom_sem:
            try:
                # 1. INSTAGRAM PROBE
                if special_handler == "instagram":
                    insta_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
                    h = {**COMMON_HEADERS, "X-IG-App-ID": "936619743392459", "Referer": f"https://www.instagram.com/{username}/"}
                    resp = await client.get(insta_url, headers=h, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        try:
                            ud = resp.json().get("data", {}).get("user", {})
                            if ud:
                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": ud.get("full_name"),
                                    "bio": ud.get("biography"),
                                    "avatar_url": ud.get("profile_pic_url_hd") or ud.get("profile_pic_url")
                                }
                        except Exception:
                            pass

                # 2. TIKTOK PROBE
                elif special_handler == "tiktok":
                    tt_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{username}"
                    resp = await client.get(tt_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("author_name") or data.get("title"):
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": data.get("author_name"),
                                "bio": data.get("title"),
                                "avatar_url": data.get("thumbnail_url")
                            }

                # 3. REDDIT PUBLIC JSON PROBE
                elif special_handler == "reddit":
                    r_url = f"https://www.reddit.com/user/{username}/about.json"
                    resp = await client.get(r_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        if data.get("name") and not data.get("is_suspended"):
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": data.get("subreddit", {}).get("title") or data.get("name"),
                                "bio": data.get("subreddit", {}).get("public_description"),
                                "avatar_url": data.get("icon_img")
                            }

                # 4. BLUESKY AT-PROTOCOL PROBE
                elif special_handler == "bluesky":
                    bsky_api = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={username}.bsky.social"
                    resp = await client.get(bsky_api, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("handle"):
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": data.get("displayName"),
                                "bio": data.get("description"),
                                "avatar_url": data.get("avatar")
                            }

                # 5. GITHUB API PROBE
                elif special_handler == "github":
                    gh_url = f"https://api.github.com/users/{username}"
                    resp = await client.get(gh_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": data.get("name"),
                            "bio": data.get("bio"),
                            "avatar_url": data.get("avatar_url"),
                            "outbound_links": [data.get("blog")] if data.get("blog") else []
                        }

                # 6. TELEGRAM WEB PROBE
                elif special_handler == "telegram":
                    tg_url = f"https://t.me/{username}"
                    resp = await client.get(tg_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    text = resp.text
                    if resp.status_code == 200 and "tgme_page_extra" in text and "If you have Telegram, you can contact" not in text:
                        result["found"] = True
                        result["metadata"] = extract_html_metadata(text)

                # 7. STEAM XML PROBE
                elif special_handler == "steam":
                    steam_url = f"https://steamcommunity.com/id/{username}/?xml=1"
                    resp = await client.get(steam_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200 and "<steamID64>" in resp.text:
                        result["found"] = True
                        meta = extract_html_metadata(resp.text)
                        st_name = re.search(r'<steamID><!\[CDATA\[(.*?)\]\]></steamID>', resp.text)
                        if st_name:
                            meta["display_name"] = st_name.group(1)
                        result["metadata"] = meta

                # 8. STANDARD MULTI-FACTOR VERIFICATION
                else:
                    resp = await client.get(url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
                    result["status_code"] = resp.status_code
                    final_url = str(resp.url).lower()
                    text = resp.text.lower()

                    # Filter login redirects
                    is_redirect_bounce = any(
                        p in final_url for p in ["/login", "/signin", "/signup", "/register", "404", "error", "/explore"]
                    ) and not (f"/{username.lower()}" in final_url or f"@{username.lower()}" in final_url)

                    # Filter challenge and error patterns
                    has_challenge_or_error = any(p in text for p in CHALLENGE_PATTERNS)

                    if resp.status_code == 200 and not is_redirect_bounce and not has_challenge_or_error:
                        result["found"] = True
                        result["metadata"] = extract_html_metadata(resp.text)
                    else:
                        result["found"] = False

            except Exception:
                result["found"] = False

    result["latency_ms"] = int((time.time() - start_time) * 1000)
    return result

async def scan_usernames_async(usernames: List[str], location: str = "") -> AsyncGenerator[Dict[str, Any], None]:
    country_info = resolve_country(location)
    target_country = country_info["code"] if country_info else ""

    # Filter catalog: include general sites + only matching regional sites
    active_catalog = []
    for site in SITES_CATALOG:
        req_country = site.get("country")
        if req_country:
            # Regional site: only include if user's country matches
            if target_country and target_country == req_country:
                active_catalog.append(site)
        else:
            active_catalog.append(site)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT, 
        verify=HTTP_VERIFY,
        limits=httpx.Limits(max_connections=MAX_CONCURRENT_REQUESTS, max_keepalive_connections=15)
    ) as client:
        for u in usernames:
            tasks = [check_single_site(client, site, u) for site in active_catalog]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                yield res