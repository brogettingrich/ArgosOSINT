import asyncio
import re
import html
import time
import hashlib
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional
from urllib.parse import urlparse
from app.config import MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT, COMMON_HEADERS, HTTP_VERIFY
from app.modules.sites_catalog import SITES_CATALOG
from app.core.permutations import resolve_country

SITES_DB = SITES_CATALOG

DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def get_domain_semaphore(url: str) -> asyncio.Semaphore:
    domain = urlparse(url).netloc
    if domain not in DOMAIN_SEMAPHORES:
        DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(3)
    return DOMAIN_SEMAPHORES[domain]

CHALLENGE_PATTERNS = [
    "cf-browser-verification",
    "challenge-platform",
    "<title>just a moment...</title>",
    "<title>attention required",
    "checking your browser before accessing",
    "sina visitor system",
    "<title>404 not found",
    "<title>page not found",
    "couldn't find this account",
    "sorry, this page isn't available",
    "this content isn't available right now"
]

def generate_avatar_fingerprint(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    clean = re.sub(r'[?&](stp|oh|oe|ccb|_nc_sid|_nc_ohc|token)=[^&]+', '', url)
    return hashlib.md5(clean.encode('utf-8')).hexdigest()[:12]

def extract_html_metadata(html_text: str) -> Dict[str, Any]:
    meta = {
        "display_name": None,
        "bio": None,
        "avatar_url": None,
        "avatar_hash": None,
        "metrics": {},
        "outbound_links": [],
        "mentioned_handles": [],
        "mentioned_emails": []
    }
    if not html_text or len(html_text) < 50:
        return meta

    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html_text, re.I)
    if not title_match:
        title_match = re.search(r'<title>(.*?)</title>', html_text, re.I)
    if title_match:
        raw_t = html.unescape(title_match.group(1)).split('|')[0].split('•')[0].split('-')[0].strip()
        if not any(c in raw_t.lower() for c in ["404", "not found", "login", "browser", "challenge", "facebook", "error"]):
            meta["display_name"] = raw_t

    desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', html_text, re.I)
    if not desc_match:
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_text, re.I)
    if desc_match:
        bio_text = html.unescape(desc_match.group(1)).strip()
        if not any(c in bio_text.lower() for c in ["404", "not found", "accept tips with 0-5%"]):
            meta["bio"] = bio_text
            meta["mentioned_handles"] = list(set(re.findall(r'@([a-zA-Z0-9._]{3,30})', bio_text)))
            meta["mentioned_emails"] = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio_text)))

            m_f = re.search(r'([\d,KkMm.]+)\s+Followers', bio_text, re.I)
            m_fg = re.search(r'([\d,KkMm.]+)\s+Following', bio_text, re.I)
            m_p = re.search(r'([\d,KkMm.]+)\s+Posts', bio_text, re.I)
            if m_f: meta["metrics"]["followers"] = m_f.group(1)
            if m_fg: meta["metrics"]["following"] = m_fg.group(1)
            if m_p: meta["metrics"]["posts"] = m_p.group(1)

    img_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html_text, re.I)
    if img_match:
        img_url = img_match.group(1).strip()
        meta["avatar_url"] = img_url
        meta["avatar_hash"] = generate_avatar_fingerprint(img_url)

    outbound = re.findall(r'href=["\'](https?://(?:www\.)?(?:linktr\.ee|beacons\.ai|carrd\.co|github\.com|twitter\.com|x\.com|t\.me|discord\.gg)/[a-zA-Z0-9._/-]+)["\']', html_text, re.I)
    meta["outbound_links"] = list(set(outbound))[:5]

    return meta

async def check_single_site(client: httpx.AsyncClient, site: Dict[str, Any], username: str, seed_name: str = "") -> Dict[str, Any]:
    u_clean = username.strip().lstrip('@').rstrip('/').lower()
    url = site["url_template"].format(u_clean)
    profile_url = site.get("profile_url", site["url_template"]).format(u_clean)
    special_handler = site.get("special_handler")

    start_time = time.time()
    result = {
        "site": site["name"],
        "category": site.get("category", "General"),
        "username": u_clean,
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
                    insta_url = f"https://www.instagram.com/{u_clean}/"
                    resp = await client.get(insta_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        text = resp.text
                        m_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', text, re.I)
                        m_desc = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', text, re.I)
                        m_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', text, re.I)

                        if m_title:
                            t_clean = html.unescape(m_title.group(1)).strip()
                            t_lower = t_clean.lower()

                            is_target_profile = (
                                f"@{u_clean}" in t_lower or 
                                f"({u_clean})" in t_lower or
                                t_lower.startswith(f"{u_clean} ") or
                                t_lower.startswith(f"{u_clean}(") or
                                f"(@{u_clean})" in t_lower
                            )

                            if is_target_profile:
                                name_part = t_clean.split('(@')[0].split('(')[0].strip()
                                desc_clean = html.unescape(m_desc.group(1)).strip() if m_desc else ""
                                img_url = m_img.group(1).strip() if m_img else None

                                metrics = {}
                                m_f = re.search(r'([\d,KkMm.]+)\s+Followers', desc_clean, re.I)
                                m_fg = re.search(r'([\d,KkMm.]+)\s+Following', desc_clean, re.I)
                                m_p = re.search(r'([\d,KkMm.]+)\s+Posts', desc_clean, re.I)
                                if m_f: metrics["followers"] = m_f.group(1)
                                if m_fg: metrics["following"] = m_fg.group(1)
                                if m_p: metrics["posts"] = m_p.group(1)

                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": name_part or u_clean,
                                    "bio": desc_clean,
                                    "avatar_url": img_url,
                                    "avatar_hash": generate_avatar_fingerprint(img_url),
                                    "metrics": metrics
                                }

                # 2. SPOTIFY PROBE
                elif special_handler == "spotify":
                    sp_url = f"https://open.spotify.com/user/{u_clean}"
                    resp = await client.get(sp_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        m_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        m_desc = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        m_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        if m_title:
                            t = html.unescape(m_title.group(1)).strip()
                            if t and "web player" not in t.lower() and not t.lower().startswith("spotify"):
                                img_url = m_img.group(1).strip() if m_img else None
                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": t,
                                    "bio": m_desc.group(1) if m_desc else "",
                                    "avatar_url": img_url,
                                    "avatar_hash": generate_avatar_fingerprint(img_url),
                                    "metrics": {}
                                }

                # 3. TWITCH PROBE
                elif special_handler == "twitch":
                    tw_url = f"https://www.twitch.tv/{u_clean}"
                    resp = await client.get(tw_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        m_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        m_desc = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        m_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', resp.text, re.I)
                        if m_title:
                            t = html.unescape(m_title.group(1)).strip()
                            if u_clean in t.lower() and "twitch" in t.lower():
                                img_url = m_img.group(1).strip() if m_img else None
                                result["found"] = True
                                result["metadata"] = {
                                    "display_name": t.split('-')[0].strip(),
                                    "bio": m_desc.group(1) if m_desc else "",
                                    "avatar_url": img_url,
                                    "avatar_hash": generate_avatar_fingerprint(img_url),
                                    "metrics": {}
                                }

                # 4. FACEBOOK PROBE
                elif special_handler == "facebook":
                    fb_url = f"https://m.facebook.com/{u_clean}"
                    h_fb = {
                        **COMMON_HEADERS,
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1"
                    }
                    resp = await client.get(fb_url, headers=h_fb, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        text = resp.text
                        m_og_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', text, re.I)
                        m_og_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', text, re.I)
                        title_m = re.search(r'<title>(.*?)</title>', text, re.I)
                        title_val = html.unescape(title_m.group(1)).strip() if title_m else ""

                        is_invalid = (
                            any(m in text.lower() for m in ["this content isn't available right now", "this page isn't available", "page not found", "log into facebook"]) or
                            title_val.lower() in ["facebook", "log in to facebook", "error"]
                        )

                        if not is_invalid:
                            display_name = html.unescape(m_og_title.group(1)).strip() if m_og_title else title_val.split('•')[0].split('(')[0].strip()
                            intro_snippets = re.findall(r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>', text, re.I)
                            intro_clean = " • ".join([re.sub(r'<[^>]+>', '', s).strip() for s in intro_snippets if s])
                            post_snippets = re.findall(r'<div[^>]*class="[^"]*story_body_container[^"]*"[^>]*>(.*?)</div>', text, re.I)
                            clean_posts = [re.sub(r'<[^>]+>', '', p).strip() for p in post_snippets[:2] if len(p) > 20]

                            bio_combined = f"Facebook: {display_name}"
                            if intro_clean:
                                bio_combined += f" | {intro_clean}"
                            if clean_posts:
                                post_preview = clean_posts[0][:120].replace('"', "'")
                                bio_combined += f" | Recent post: '{post_preview}'"

                            img_url = m_og_img.group(1).strip() if m_og_img else None
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": display_name,
                                "bio": bio_combined,
                                "avatar_url": img_url,
                                "avatar_hash": generate_avatar_fingerprint(img_url),
                                "metrics": {}
                            }

                # 5. TIKTOK PROBE
                elif special_handler == "tiktok":
                    tt_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{u_clean}"
                    resp = await client.get(tt_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("author_name") or data.get("title"):
                            img_url = data.get("thumbnail_url")
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": data.get("author_name"),
                                "bio": data.get("title"),
                                "avatar_url": img_url,
                                "avatar_hash": generate_avatar_fingerprint(img_url),
                                "metrics": {}
                            }

                # 6. REDDIT PROBE
                elif special_handler == "reddit":
                    r_url = f"https://old.reddit.com/user/{u_clean}"
                    resp = await client.get(r_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        result["found"] = True
                        result["metadata"] = extract_html_metadata(resp.text)

                # 7. GITHUB API PROBE
                elif special_handler == "github":
                    gh_url = f"https://api.github.com/users/{u_clean}"
                    resp = await client.get(gh_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200:
                        data = resp.json()
                        img_url = data.get("avatar_url")
                        metrics = {}
                        if "followers" in data: metrics["followers"] = str(data.get("followers"))
                        if "following" in data: metrics["following"] = str(data.get("following"))
                        if "public_repos" in data: metrics["repos"] = str(data.get("public_repos"))

                        bio_str = data.get("bio") or ""
                        if data.get("company"): bio_str += f" | {data.get('company')}"
                        if data.get("location"): bio_str += f" | {data.get('location')}"

                        outbound = []
                        if data.get("blog"): outbound.append(data.get("blog"))
                        if data.get("twitter_username"): outbound.append(f"https://x.com/{data.get('twitter_username')}")

                        result["found"] = True
                        result["metadata"] = {
                            "display_name": data.get("name") or u_clean,
                            "bio": bio_str.strip(" | "),
                            "avatar_url": img_url,
                            "avatar_hash": generate_avatar_fingerprint(img_url),
                            "metrics": metrics,
                            "outbound_links": outbound
                        }

                # 8. TELEGRAM WEB PROBE
                elif special_handler == "telegram":
                    tg_url = f"https://t.me/{u_clean}"
                    resp = await client.get(tg_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    text = resp.text
                    if resp.status_code == 200 and "tgme_page_extra" in text and "If you have Telegram, you can contact" not in text:
                        result["found"] = True
                        result["metadata"] = extract_html_metadata(text)

                # 9. STEAM XML PROBE
                elif special_handler == "steam":
                    steam_url = f"https://steamcommunity.com/id/{u_clean}/?xml=1"
                    resp = await client.get(steam_url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT)
                    result["status_code"] = resp.status_code
                    if resp.status_code == 200 and "<steamID64>" in resp.text:
                        result["found"] = True
                        meta = extract_html_metadata(resp.text)
                        st_name = re.search(r'<steamID><!\[CDATA\[(.*?)\]\]></steamID>', resp.text)
                        st_avatar = re.search(r'<avatarFull><!\[CDATA\[(.*?)\]\]></avatarFull>', resp.text)
                        if st_name:
                            meta["display_name"] = st_name.group(1)
                        if st_avatar:
                            meta["avatar_url"] = st_avatar.group(1)
                            meta["avatar_hash"] = generate_avatar_fingerprint(st_avatar.group(1))
                        result["metadata"] = meta

                # 10. STANDARD MULTI-FACTOR VERIFICATION
                else:
                    resp = await client.get(url, headers=COMMON_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
                    result["status_code"] = resp.status_code
                    final_url = str(resp.url).lower()
                    text = resp.text.lower()

                    is_handle_in_url = (
                        f"/{u_clean}" in final_url or 
                        f"@{u_clean}" in final_url or 
                        f"//{u_clean}." in final_url or 
                        f".{u_clean}." in final_url
                    )

                    is_redirect_bounce = any(
                        p in final_url for p in ["/login", "/signin", "/signup", "/register", "404", "error", "/explore"]
                    ) and not is_handle_in_url

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

async def scan_usernames_async(usernames: List[str], location: str = "", seed_name: str = "") -> AsyncGenerator[Dict[str, Any], None]:
    country_info = resolve_country(location)
    target_country = country_info["code"] if country_info else ""

    active_catalog = []
    for site in SITES_CATALOG:
        req_country = site.get("country")
        if req_country:
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
            tasks = [check_single_site(client, site, u, seed_name=seed_name) for site in active_catalog]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                yield res