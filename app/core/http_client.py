import asyncio
import random
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, HTTP_VERIFY, MAX_CONCURRENT_REQUESTS

DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def get_domain_semaphore(url: str, max_per_domain: int = 4) -> asyncio.Semaphore:
    domain = urlparse(url).netloc
    if domain not in DOMAIN_SEMAPHORES:
        DOMAIN_SEMAPHORES[domain] = asyncio.Semaphore(max_per_domain)
    return DOMAIN_SEMAPHORES[domain]

def create_async_client(timeout: float = REQUEST_TIMEOUT) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=COMMON_HEADERS,
        timeout=timeout,
        verify=HTTP_VERIFY,
        limits=httpx.Limits(
            max_connections=MAX_CONCURRENT_REQUESTS,
            max_keepalive_connections=20,
            keepalive_expiry=15.0
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
    dom_sem = get_domain_semaphore(url)
    h = headers or COMMON_HEADERS

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

                    # If rate limited (429) or transient 503/504, retry with exponential backoff & jitter
                    if resp.status_code in (429, 502, 503, 504) and attempt < max_retries:
                        backoff = (0.3 * (2 ** attempt)) + random.uniform(0.05, 0.15)
                        await asyncio.sleep(backoff)
                        continue

                    return resp
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
                    if attempt < max_retries:
                        backoff = (0.2 * (2 ** attempt)) + random.uniform(0.05, 0.1)
                        await asyncio.sleep(backoff)
                    else:
                        raise