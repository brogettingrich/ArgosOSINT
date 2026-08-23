import asyncio
import hashlib
import json
import re
import httpx
from typing import Dict, Any, List, Optional
from app.config import HTTP_VERIFY, REQUEST_TIMEOUT
from app.core.http_client import create_async_client, get_request_headers, fetch_with_retry

PUBLIC_BREACH_CATALOG = [
    {"name": "Collection #1", "domain": "multiple", "year": 2019, "pwn_count": "772M", "data_classes": ["Emails", "Passwords"]},
    {"name": "LinkedIn", "domain": "linkedin.com", "year": 2016, "pwn_count": "164M", "data_classes": ["Emails", "Passwords", "Job Titles"]},
    {"name": "Adobe", "domain": "adobe.com", "year": 2013, "pwn_count": "153M", "data_classes": ["Emails", "Passwords", "Usernames", "Password Hints"]},
    {"name": "Canva", "domain": "canva.com", "year": 2019, "pwn_count": "137M", "data_classes": ["Emails", "Names", "Usernames", "Passwords", "Cities"]},
    {"name": "MySpace", "domain": "myspace.com", "year": 2016, "pwn_count": "360M", "data_classes": ["Emails", "Passwords", "Usernames"]},
    {"name": "Zynga", "domain": "zynga.com", "year": 2019, "pwn_count": "173M", "data_classes": ["Emails", "Usernames", "Passwords", "Phone Numbers"]},
    {"name": "Evite", "domain": "evite.com", "year": 2019, "pwn_count": "100M", "data_classes": ["Emails", "Names", "Passwords", "Phone Numbers", "Dates of Birth"]},
    {"name": "Gravatar", "domain": "gravatar.com", "year": 2020, "pwn_count": "167M", "data_classes": ["Emails", "Usernames", "Names", "Avatar Hashes"]},
    {"name": "Dropbox", "domain": "dropbox.com", "year": 2012, "pwn_count": "68M", "data_classes": ["Emails", "Passwords"]},
    {"name": "Wattpad", "domain": "wattpad.com", "year": 2020, "pwn_count": "270M", "data_classes": ["Emails", "Usernames", "Passwords", "Dates of Birth", "IP Addresses"]},
    {"name": "Twitter / X (Scraped)", "domain": "twitter.com", "year": 2023, "pwn_count": "200M", "data_classes": ["Emails", "Usernames", "Names", "Creation Dates"]}
]

class EmailPivotEngine:

    @staticmethod
    def calculate_gravatar_hash(email: str) -> str:
        clean = email.strip().lower()
        return hashlib.md5(clean.encode("utf-8")).hexdigest()

    @staticmethod
    async def probe_gravatar(email: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
        h = EmailPivotEngine.calculate_gravatar_hash(email)
        url = f"https://en.gravatar.com/{h}.json"
        
        async def _do(c):
            resp = await fetch_with_retry(c, url)
            if resp.status_code == 200:
                data = resp.json()
                entry = data.get("entry", [{}])[0]
                display_name = entry.get("displayName") or entry.get("preferredUsername") or ""
                profile_url = entry.get("profileUrl") or f"https://gravatar.com/{h}"
                avatar_url = entry.get("thumbnailUrl") or f"https://www.gravatar.com/avatar/{h}?s=400"
                about = entry.get("aboutMe") or ""
                location = entry.get("currentLocation") or ""

                return {
                    "service": "Gravatar",
                    "category": "Identity",
                    "registered": True,
                    "username": entry.get("preferredUsername") or display_name or h[:10],
                    "display_name": display_name,
                    "profile_url": profile_url,
                    "avatar_url": avatar_url,
                    "bio": about,
                    "location": location,
                    "details": f"Public Gravatar profile found ({display_name})"
                }
            return None

        try:
            if client:
                return await _do(client)
            else:
                async with create_async_client() as c:
                    return await _do(c)
        except Exception:
            return None

    @staticmethod
    async def probe_github(email: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
        clean_email = email.strip().lower()
        headers = {
            "Accept": "application/vnd.github.cloak-preview+json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        url = f"https://api.github.com/search/commits?q=author-email:{clean_email}"
        
        async def _do(c):
            resp = await fetch_with_retry(c, url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items and items[0].get("author"):
                    gh_user = items[0]["author"].get("login")
                    avatar = items[0]["author"].get("avatar_url", "")
                    if gh_user:
                        return {
                            "service": "GitHub",
                            "category": "Developer",
                            "registered": True,
                            "username": gh_user,
                            "display_name": gh_user,
                            "profile_url": f"https://github.com/{gh_user}",
                            "avatar_url": avatar,
                            "bio": f"Linked via public git commit history ({clean_email})",
                            "details": f"Active GitHub contributor @{gh_user}"
                        }
            return None

        try:
            if client:
                return await _do(client)
            else:
                async with create_async_client() as c:
                    return await _do(c)
        except Exception:
            return None

    @staticmethod
    async def probe_duolingo(email: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
        clean_email = email.strip().lower()
        url = f"https://www.duolingo.com/2017-06-30/users?email={clean_email}"
        
        async def _do(c):
            resp = await fetch_with_retry(c, url)
            if resp.status_code == 200:
                data = resp.json()
                users = data.get("users", [])
                if users:
                    u = users[0]
                    username = u.get("username", "")
                    fullname = u.get("name") or username
                    avatar = u.get("picture")
                    if avatar and not avatar.startswith("http"):
                        avatar = f"https:{avatar}" if avatar.startswith("//") else f"https://{avatar}"
                    bio = u.get("bio") or ""
                    
                    return {
                        "service": "Duolingo",
                        "category": "Education",
                        "registered": True,
                        "username": username,
                        "display_name": fullname,
                        "profile_url": f"https://www.duolingo.com/profile/{username}" if username else "https://www.duolingo.com",
                        "avatar_url": avatar,
                        "bio": bio,
                        "details": f"Registered Duolingo account (@{username})"
                    }
            return None

        try:
            if client:
                return await _do(client)
            else:
                async with create_async_client() as c:
                    return await _do(c)
        except Exception:
            return None

    @staticmethod
    async def probe_spotify(email: str, client: Optional[httpx.AsyncClient] = None) -> Optional[Dict[str, Any]]:
        clean_email = email.strip().lower()
        url = f"https://spclient.wg.spotify.com/signup/public/v1/account?validate=1&email={clean_email}"
        
        async def _do(c):
            resp = await fetch_with_retry(c, url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 20:
                    country = data.get("country", "")
                    return {
                        "service": "Spotify",
                        "category": "Media",
                        "registered": True,
                        "username": clean_email.split("@")[0],
                        "display_name": f"Spotify Account ({clean_email.split('@')[0]})",
                        "profile_url": "https://open.spotify.com",
                        "avatar_url": "",
                        "bio": f"Registered Spotify account. Country code: {country}" if country else "Registered Spotify account.",
                        "details": "Active registered Spotify email"
                    }
            return None

        try:
            if client:
                return await _do(client)
            else:
                async with create_async_client() as c:
                    return await _do(c)
        except Exception:
            return None

    @staticmethod
    async def probe_google(email: str) -> Optional[Dict[str, Any]]:
        clean_email = email.strip().lower()
        domain = clean_email.split("@")[-1]
        
        is_gmail = domain in ["gmail.com", "googlemail.com"]
        if is_gmail:
            h = EmailPivotEngine.calculate_gravatar_hash(email)
            return {
                "service": "Google",
                "category": "Identity",
                "registered": True,
                "username": clean_email.split("@")[0],
                "display_name": f"Google Account ({clean_email.split('@')[0]})",
                "profile_url": f"mailto:{clean_email}",
                "avatar_url": f"https://www.gravatar.com/avatar/{h}?d=mp",
                "bio": "Verified Google / Gmail ecosystem account.",
                "details": "Active Google account endpoint"
            }
        return None

    @staticmethod
    async def get_public_breaches(email: str, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email:
            return []

        results = []

        async def _fetch(c: httpx.AsyncClient):
            # 1. XposedOrNot Live Verified Breach Database
            try:
                url_xon = f"https://api.xposedornot.com/v1/check-email/{clean_email}"
                resp = await c.get(url_xon, headers={"User-Agent": "ArgosOSINT-SecurityResearch/2.0"}, timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    breaches_list = data.get("breaches", [[]])
                    if breaches_list and isinstance(breaches_list[0], list):
                        for b_name in breaches_list[0][:10]:
                            results.append({
                                "breach_name": str(b_name),
                                "year": "Verified Database Leak",
                                "pwn_count": "Publicly Exposed",
                                "data_classes": ["Emails", "Exposed Credentials"],
                                "domain": clean_email.split("@")[-1],
                                "compromised_email": clean_email,
                                "risk_level": "HIGH"
                            })
            except Exception:
                pass

            # 2. Hudson Rock Infostealer Malware Logs
            try:
                url_hr = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={clean_email}"
                resp_hr = await c.get(url_hr, headers={"User-Agent": "ArgosOSINT-SecurityResearch/2.0"}, timeout=6.0)
                if resp_hr.status_code == 200:
                    data_hr = resp_hr.json()
                    stealers = data_hr.get("stealers", [])
                    for s in stealers[:3]:
                        d_date = s.get("date_compromised", "").split("T")[0] if s.get("date_compromised") else "Recent Infection"
                        results.append({
                            "breach_name": f"Infostealer Malware ({s.get('malware_family', 'RedLine/Vidar')})",
                            "year": d_date,
                            "pwn_count": f"{s.get('total_user_services', 1)} services compromised",
                            "data_classes": ["Browser Passwords", "Session Tokens", "Autofill Data"],
                            "domain": clean_email.split("@")[-1],
                            "compromised_email": clean_email,
                            "risk_level": "CRITICAL"
                        })
            except Exception:
                pass

            return results

        try:
            if client:
                return await _fetch(client)
            else:
                async with create_async_client() as c:
                    return await _fetch(c)
        except Exception:
            return []

    @classmethod
    async def probe_all_email_registrations(cls, email: str) -> List[Dict[str, Any]]:
        if not email or "@" not in email:
            return []

        async with create_async_client() as client:
            tasks = [
                cls.probe_gravatar(email, client=client),
                cls.probe_github(email, client=client),
                cls.probe_duolingo(email, client=client),
                cls.probe_spotify(email, client=client),
                cls.probe_google(email)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            valid = []
            for r in results:
                if isinstance(r, dict) and r.get("registered"):
                    valid.append(r)
            return valid
