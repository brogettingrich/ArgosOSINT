import asyncio
import re
import html
import time
import json
import hashlib
import httpx
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.config import MAX_CONCURRENT_REQUESTS, REQUEST_TIMEOUT, COMMON_HEADERS, HTTP_VERIFY
from app.modules.sites_catalog import SITES_CATALOG
from app.core.permutations import resolve_country
from app.core.http_client import safe_get

SITES_DB = SITES_CATALOG

# Expanded list of "dead page" markers. Prevents soft-404 pages from being
# mistaken for real profiles (many platforms return HTTP 200 for unknown users).
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
    "couldn't find that page",
    "sorry, this page isn't available",
    "this content isn't available right now",
    "that page doesn’t exist",
    "that page doesn't exist",
    "the page you were looking for was not found",
    "no account found with that",
    "this account doesn't exist",
    "this account does not exist",
    "profile not found",
    "page you're looking for doesn't exist",
    "the specified user does not exist",
    "resource does not exist"
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
        img_url = html.unescape(img_match.group(1)).strip()
        if img_url:
            meta["avatar_url"] = img_url
            meta["avatar_hash"] = generate_avatar_fingerprint(img_url)

    # Outbound social cross-links (used for corroboration)
    link_matches = re.findall(
        r'https?://(?:www\.)?(?:twitter\.com|instagram\.com|tiktok\.com|github\.com|youtube\.com|twitch\.tv|t\.me|wa\.me|discord\.gg|facebook\.com|tumblr\.com|reddit\.com|mastodon\.social|bsky\.app)/[A-Za-z0-9_./@%+-]+',
        html_text
    )
    meta["outbound_links"] = list(dict.fromkeys(link_matches))[:6]

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

    try:
        # 1. INSTAGRAM PROBE
        if special_handler == "instagram":
            insta_url = f"https://www.instagram.com/{u_clean}/"
            resp = await safe_get(client, insta_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
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
            resp = await safe_get(client, sp_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
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
            resp = await safe_get(client, tw_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
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
            resp = await safe_get(client, fb_url, headers=h_fb)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
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

        # 5. TIKTOK PROBE (public oEmbed endpoint)
        elif special_handler == "tiktok":
            tt_url = f"https://www.tiktok.com/oembed?url=https://www.tiktok.com/@{u_clean}"
            resp = await safe_get(client, tt_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    author = data.get("author_name") or ""
                    if author:
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": author,
                            "bio": (data.get("title") or "")[:300],
                            "avatar_url": None,
                            "avatar_hash": None,
                            "metrics": {}
                        }
                except Exception:
                    pass

        # 6. REDDIT PROBE (public JSON API)
        elif special_handler == "reddit":
            red_url = f"https://www.reddit.com/user/{u_clean}/about.json"
            resp = await safe_get(client, red_url, headers={**COMMON_HEADERS, "User-Agent": "ArgosOSINT/3.2 (OSINT research)"})
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    rd = data.get("data", {})
                    if rd and rd.get("name"):
                        sub = rd.get("subreddit", {})
                        if isinstance(sub, dict):
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": sub.get("title") or rd.get("name"),
                                "bio": sub.get("description") or "",
                                "avatar_url": rd.get("icon_img") or sub.get("icon_img"),
                                "avatar_hash": generate_avatar_fingerprint(rd.get("icon_img")),
                                "metrics": {
                                    "followers": sub.get("subscribers"),
                                    "karma": rd.get("total_karma")
                                }
                            }
                except Exception:
                    pass

        # 7. GITHUB PROBE (public API)
        elif special_handler == "github":
            gh_url = f"https://api.github.com/users/{u_clean}"
            resp = await safe_get(client, gh_url, headers={**COMMON_HEADERS, "Accept": "application/vnd.github+json"})
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("login"):
                        blog = data.get("blog") or ""
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": data.get("name") or data.get("login"),
                            "bio": data.get("bio") or "",
                            "avatar_url": data.get("avatar_url"),
                            "avatar_hash": generate_avatar_fingerprint(data.get("avatar_url")),
                            "metrics": {
                                "repos": data.get("public_repos"),
                                "followers": data.get("followers"),
                                "following": data.get("following")
                            },
                            "outbound_links": [blog] if blog and blog.startswith("http") else []
                        }
                except Exception:
                    pass

        # 8. TELEGRAM PROBE
        elif special_handler == "telegram":
            tg_url = f"https://t.me/{u_clean}"
            resp = await safe_get(client, tg_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                text = resp.text
                if "tgme_page_extra" in text and "If you have Telegram, you can contact" not in text:
                    m_name = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', text, re.I)
                    m_desc = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', text, re.I)
                    m_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', text, re.I)
                    img_url = m_img.group(1).strip() if m_img else None
                    result["found"] = True
                    result["metadata"] = {
                        "display_name": html.unescape(m_name.group(1)).strip() if m_name else u_clean,
                        "bio": html.unescape(m_desc.group(1)).strip() if m_desc else "",
                        "avatar_url": img_url,
                        "avatar_hash": generate_avatar_fingerprint(img_url),
                        "metrics": {}
                    }

        # 9. STEAM PROBE (public XML endpoint)
        elif special_handler == "steam":
            steam_url = f"https://steamcommunity.com/id/{u_clean}/?xml=1"
            resp = await safe_get(client, steam_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200 and "<steamID64>" in resp.text:
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

        # 10. TWITTER / X PROBE (public oEmbed endpoint - avoids login-wall soft-404s)
        elif special_handler == "twitter":
            tw_url = f"https://publish.twitter.com/oembed?url=https://twitter.com/{u_clean}"
            resp = await safe_get(client, tw_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    author = data.get("author_name") or ""
                    if author:
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": author,
                            "bio": "",
                            "avatar_url": None,
                            "avatar_hash": None,
                            "metrics": {}
                        }
                except Exception:
                    pass

        # 11. PINTEREST PROBE (JSON profile markers inside page)
        elif special_handler == "pinterest":
            pin_url = f"https://www.pinterest.com/{u_clean}/"
            resp = await safe_get(client, pin_url, headers=COMMON_HEADERS, follow_redirects=True)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                text = resp.text
                low = text.lower()
                dead = any(p in low for p in ["this account does not exist", "resource does not exist", "page not found", "not available"])
                profile_ref = re.search(r'"profile_name"\s*:\s*"' + re.escape(u_clean) + r'"', text, re.I)
                profile_ref2 = re.search(r'"username"\s*:\s*"' + re.escape(u_clean) + r'"', text, re.I)
                if not dead and (profile_ref or profile_ref2):
                    meta = extract_html_metadata(text)
                    result["found"] = True
                    result["metadata"] = meta

        # 12. SNAPCHAT PROBE (final URL + profile markers)
        elif special_handler == "snapchat":
            sn_url = f"https://www.snapchat.com/add/{u_clean}"
            resp = await safe_get(client, sn_url, headers=COMMON_HEADERS, follow_redirects=True)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                final_url = str(resp.url).lower()
                text = resp.text.lower()
                if f"/add/{u_clean}" in final_url and ("displayname" in text or "snapcode" in text or "bitmoji" in text):
                    result["found"] = True
                    result["metadata"] = extract_html_metadata(resp.text)

        # 13. YOUTUBE PROBE (returns 404 for non-existent channels)
        elif special_handler == "youtube":
            yt_url = f"https://www.youtube.com/@{u_clean}"
            resp = await safe_get(client, yt_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                text = resp.text
                low = text.lower()
                if any(p in low for p in ["this channel does not exist", "channel not found", "page not found"]):
                    pass
                else:
                    meta = extract_html_metadata(text)
                    m_name = re.search(r'"displayName":"(.*?)"', text)
                    if m_name:
                        try:
                            meta["display_name"] = json.loads('"' + m_name.group(1) + '"')
                        except Exception:
                            meta["display_name"] = m_name.group(1)
                    if meta.get("display_name"):
                        result["found"] = True
                        result["metadata"] = meta

        # 14. BLUESKY PROBE (public AT-Protocol API)
        elif special_handler == "bluesky":
            bsky_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={u_clean}"
            resp = await safe_get(client, bsky_url, headers={"User-Agent": COMMON_HEADERS["User-Agent"]})
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("handle"):
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": data.get("displayName") or data.get("handle"),
                            "bio": data.get("description") or "",
                            "avatar_url": data.get("avatar"),
                            "avatar_hash": generate_avatar_fingerprint(data.get("avatar")),
                            "metrics": {
                                "followers": data.get("followersCount"),
                                "following": data.get("followsCount")
                            }
                        }
                except Exception:
                    pass

        # 15. MASTODON PROBE (public lookup API)
        elif special_handler == "mastodon":
            ms_url = f"https://mastodon.social/api/v1/accounts/lookup?acct={u_clean}"
            resp = await safe_get(client, ms_url, headers={"User-Agent": COMMON_HEADERS["User-Agent"]})
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get("username"):
                        bio = re.sub(r'<[^>]+>', '', data.get("note", "")).strip()
                        result["found"] = True
                        result["metadata"] = {
                            "display_name": data.get("display_name") or data.get("username"),
                            "bio": bio,
                            "avatar_url": data.get("avatar"),
                            "avatar_hash": generate_avatar_fingerprint(data.get("avatar")),
                            "metrics": {
                                "followers": data.get("followers_count"),
                                "following": data.get("following_count")
                            }
                        }
                except Exception:
                    pass

        # 16. MEDIUM PROBE (JSON-wrapped profile endpoint)
        elif special_handler == "medium":
            md_url = f"https://medium.com/@{u_clean}?format=json"
            resp = await safe_get(client, md_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200:
                raw = resp.text
                body = raw[raw.find('{'):] if '{' in raw else ""
                if body:
                    try:
                        data = json.loads(body)
                        payload = data.get("payload", {})
                        user = payload.get("user", {})
                        if user and user.get("name") and u_clean.lower() in str(user.get("username", "")).lower():
                            img_id = user.get("imageId")
                            result["found"] = True
                            result["metadata"] = {
                                "display_name": user.get("name"),
                                "bio": user.get("bio") or "",
                                "avatar_url": f"https://cdn-images-1.medium.com/fit/c/200/200/{img_id}" if img_id else None,
                                "avatar_hash": generate_avatar_fingerprint(img_id),
                                "metrics": {
                                    "followers": payload.get("socialStats", {}).get("followerCount")
                                }
                            }
                    except Exception:
                        pass

        # 17. SUBSTACK PROBE (public RSS feed - 404 for non-existent blogs)
        elif special_handler == "substack":
            sb_url = f"https://{u_clean}.substack.com/feed"
            resp = await safe_get(client, sb_url, headers=COMMON_HEADERS)
            result["status_code"] = resp.status_code if resp else 0
            if resp and resp.status_code == 200 and "<rss" in resp.text.lower():
                m_title = re.search(r'<title>(.*?)</title>', resp.text, re.I)
                m_desc = re.search(r'<description>(.*?)</description>', resp.text, re.I)
                result["found"] = True
                result["metadata"] = {
                    "display_name": html.unescape(m_title.group(1).strip()) if m_title else u_clean,
                    "bio": html.unescape(m_desc.group(1).strip())[:300] if m_desc else "",
                    "avatar_url": None,
                    "avatar_hash": None,
                    "metrics": {}
                }

        # 18. STANDARD MULTI-FACTOR VERIFICATION
        else:
            resp = await safe_get(client, url, headers=COMMON_HEADERS, follow_redirects=True)
            result["status_code"] = resp.status_code if resp else 0
            if resp:
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
        # Pipeline ALL (username x platform) probes concurrently for the whole
        # batch instead of draining one username at a time. Global + per-domain
        # semaphores live inside http_client.fetch_with_retry, so connection
        # fairness and rate-limit protection still apply across the whole batch.
        tasks = [
            check_single_site(client, site, u, seed_name=seed_name)
            for u in usernames
            for site in active_catalog
        ]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            yield res

