import asyncio
import random
import time
import httpx
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from app.config import REQUEST_TIMEOUT, HTTP_VERIFY, MAX_CONCURRENT_REQUESTS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
]

DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
DOMAIN_COOLDOWNS: Dict[str, float] = {}
DOMAIN_FAIL_COUNTS: Dict[str, int] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)

def get_request_headers(custom_ua: Optional[str] = None) -> Dict[str, str]:
    return {
        "User-Agent": custom_ua or get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

def get_domain_semaphore(url: str, max_per_domain: int = 4) -> asyncio.Semaphore:
    domain = urlparse(url).netloc
    if domain not in DOMAIN_SEMAPHORES:
        DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(max_per_domain)
    return DOMAIN_SEMAPHORES[domain]

def create_async_client(timeout: float = REQUEST_TIMEOUT) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        verify=HTTP_VERIFY,
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=MAX_CONCURRENT_REQUESTS,
            max_keepalive_connections=25,
            keepalive_expiry=20.0
        )
    )

async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Any] = None,
    max_retries: int = 2,
    follow_redirects: bool = True
) -> httpx.Response:
    domain = urlparse(url).netloc
    dom_sem = get_domain_semaphore(url)

    # 1. Rate-Limit Awareness & Cooldown Gate per Domain
    now = time.time()
    if domain in DOMAIN_COOLDOWNS and DOMAIN_COOLDOWNS[domain] > now:
        wait_time = DOMAIN_COOLDOWNS[domain] - now
        if wait_time > 0 and wait_time < 5.0:
            await asyncio.sleep(wait_time)

    h = headers or get_request_headers()

    for attempt in range(max_retries + 1):
        async with GLOBAL_SEMAPHORE:
            async with dom_sem:
                try:
                    if method.upper() == "GET":
                        resp = await client.get(url, headers=h, follow_redirects=follow_redirects)
                    elif method.upper() == "POST":
                        resp = await client.post(url, headers=h, json=json_body, follow_redirects=follow_redirects)
                    else:
                        resp = await client.request(method, url, headers=h, json=json_body, follow_redirects=follow_redirects)

                    # Handle 429 Rate Limit or 503 Service Unavailable
                    if resp.status_code in (429, 502, 503, 504):
                        fail_cnt = DOMAIN_FAIL_COUNTS.get(domain, 0) + 1
                        DOMAIN_FAIL_COUNTS[domain] = fail_cnt
                        backoff = (0.5 * (2 ** min(fail_cnt, 4))) + random.uniform(0.1, 0.3)
                        DOMAIN_COOLDOWNS[domain] = time.time() + backoff

                        if attempt < max_retries:
                            await asyncio.sleep(backoff)
                            continue

                    # Reset domain failures on success
                    if resp.status_code == 200:
                        DOMAIN_FAIL_COUNTS[domain] = max(0, DOMAIN_FAIL_COUNTS.get(domain, 0) - 1)

                    return resp
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
                    fail_cnt = DOMAIN_FAIL_COUNTS.get(domain, 0) + 1
                    DOMAIN_FAIL_COUNTS[domain] = fail_cnt
                    backoff = (0.3 * (2 ** min(fail_cnt, 3))) + random.uniform(0.05, 0.15)
                    DOMAIN_COOLDOWNS[domain] = time.time() + backoff

                    if attempt < max_retries:
                        await asyncio.sleep(backoff)
                    else:
                        raise