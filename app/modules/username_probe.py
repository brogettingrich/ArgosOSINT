import asyncio
import re
import time
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from urllib.parse import urlparse
from app.config import MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT, COMMON_HEADERS, HTTP_VERIFY
from app.modules.sites_catalog import SITES_CATALOG

# Shared database reference
SITES_DB = SITES_CATALOG

# Domain concurrency semaphores to protect against domain-level rate limits
DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def get_domain_semaphore(url: str) -> asyncio.Semaphore:
    domain = urlparse(url).netloc
    if domain not in DOMAIN_SEMAPHORES:
        DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(4)
    return DOMAIN_SEMAPHORES[domain]

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

    # 1. og:title / Title tag
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.I)
    if not title_match:
        title_match = re.search(r'<title>(.*?)</title>', html, re.I)
    if title_match:
        meta["display_name"] = title_match.group(1).split('|')[0].split('•')[0].split('-')[0].strip()

    # 2. og:description / Bio
    desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', html, re.I)
    if not desc_match:
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.I)
    if desc_match:
        bio_text = desc_match.group(1).strip()
        meta["bio"] = bio_text
        meta["mentioned_handles"] = list(set(re.findall(r'@([a-zA-Z0-9._]{3,30})', bio_text)))
        meta["mentioned_emails"] = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio_text)))

    # 3. og:image / Avatar
    img_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html, re.I)
    if img_match:
        meta["avatar_url"] = img_match.group(1).strip()

    # 4. Outbound links (Linktree, personal websites, etc.)
    outbound = re.findall(r'href=["\'](https?://(?:www\.)?(?:linktr\.ee|beacons\.ai|carrd\.co|github\.com|twitter\.com|x\.com|t\.me)/[a-zA-Z0-9._/-]+)["\']', html, re.I)
    meta["outbound_links"] = list(set(outbound))[:5]

    return meta

async def check_single_site(client: httpx.AsyncClient, site: Dict[str, Any], username: str) -> Dict[str, Any]:
    url = site["url_template"].format(username)
    profile_url = site.get("profile_url", site["url_template"]).format(username)
    handler_type = site.get("check_type", "status_code")
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
                # -------------------------------------------------------------
                # SPECIALIZED API PROBES (Anti-False-Positive Handlers)
                # -------------------------------------------------------------
                if special_handler == "instagram":
                    # Probe Instagram Web / Mobile API
                    insta_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
                    h = {**COMMON_HEADERS, "X-IG-App-ID": "936619743392459", "Referer": f"https://www.instagram.com/{username}/"}
                    resp = await client.get(insta_url, headers=h, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        try:
                            user_data = resp.json().get("data", {}).get("user", {})
                            if user_data:
                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": user_data.get("full_name"),
                                    "bio": user_data.get("biography"),
                                    "avatar_url": user_data.get("profile_pic_url_hd") or user_data.get("profile_pic_url"),
                                    "is_verified": user_data.get("is_verified", False)
                                }
                        except Exception:
                            result["found"] = True

                elif special_handler == "tiktok":
                    # Probe TikTok public OEMBED API
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

                elif special_handler == "reddit":
                    # Probe Reddit public JSON API
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

                elif special_handler == "github":
                    # Probe GitHub API
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
                            "location": data.get("location"),
                            "outbound_links": [data.get("blog")] if data.get("blog") else []
                        }

                elif special_handler == "telegram":
                    # Probe Telegram Web preview
                    tg_url = f"https://t.me/{username}"
                    resp = await client.get(tg_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    text = resp.text
                    if resp.status_code == 200:
                        # If t.me has real account, it has extraview or action buttons
                        if "tgme_page_extra" in text and "If you have Telegram, you can contact" not in text:
                            result["found"] = True
                            result["metadata"] = extract_html_metadata(text)

                elif special_handler == "steam":
                    # Probe Steam XML profile
                    steam_url = f"https://steamcommunity.com/id/{username}/?xml=1"
                    resp = await client.get(steam_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200 and "<steamID64>" in resp.text:
                        result["found"] = True
                        meta = extract_html_metadata(resp.text)
                        # Extract Steam display name
                        st_name = re.search(r'<steamID><!\[CDATA\[(.*?)\]\]></steamID>', resp.text)
                        if st_name:
                            meta["display_name"] = st_name.group(1)
                        result["metadata"] = meta

                elif special_handler == "pinterest":
                    # Probe Pinterest API endpoint
                    pin_url = f"https://www.pinterest.com/resource/UserResource/get/?data=%7B%22options%22%3A%7B%22username%22%3A%22{username}%22%7D%7D"
                    h = {**COMMON_HEADERS, "X-Requested-With": "XMLHttpRequest"}
                    resp = await client.get(pin_url, headers=h, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        try:
                            user_data = resp.json().get("resource_response", {}).get("data", {})
                            if user_data and user_data.get("username"):
                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": user_data.get("full_name"),
                                    "bio": user_data.get("about"),
                                    "avatar_url": user_data.get("image_xlarge_url")
                                }
                        except Exception:
                            pass

                # -------------------------------------------------------------
                # STANDARD MULTI-FACTOR VERIFICATION (MFVP Protocol)
                # -------------------------------------------------------------
                else:
                    resp = await client.get(url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
                    result["status_code"] = resp.status_code
                    final_url = str(resp.url).lower()
                    text = resp.text

                    # Tier 1: Reject redirect bounces to login, register, 404 pages
                    is_redirect_bounce = any(
                        p in final_url for p in ["/login", "/signin", "/signup", "/register", "404", "error", "/explore"]
                    ) and not (f"/{username.lower()}" in final_url or f"@{username.lower()}" in final_url)

                    # Tier 2: Check presence and error indicators
                    if resp.status_code == 200 and not is_redirect_bounce:
                        err_msg = site.get("error_message")
                        if err_msg and err_msg.lower() in text.lower():
                            result["found"] = False
                        else:
                            result["found"] = True
                            result["metadata"] = extract_html_metadata(text)
                    else:
                        result["found"] = False

            except Exception:
                result["found"] = False

    result["latency_ms"] = int((time.time() - start_time) * 1000)
    return result

async def scan_usernames_async(usernames: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT, 
        verify=HTTP_VERIFY,
        limits=httpx.Limits(max_connections=MAX_CONCURRENT_REQUESTS, max_keepalive_connections=15)
    ) as client:
        for u in usernames:
            tasks = [check_single_site(client, site, u) for site in SITES_CATALOG]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                yield res