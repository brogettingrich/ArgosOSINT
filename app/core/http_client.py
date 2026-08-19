import asyncio
import random
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from app.config import COMMON_HEADERS, REQUEST_TIMEOUT, HTTP_VERIFY, MAX_CONCURRENT_REQUESTS

# Module-level semaphores are bound lazily on first use (Python 3.10+).
DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {}
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Statuses that trigger a retry (rate-limit + transient / Cloudflare 5xx family).
RETRY_STATUSES = {408, 429, 500, 502, 503, 504, 520, 522, 524, 525, 530}

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
    follow_redirects: bool = True,
    timeout: Optional[float] = None
) -> httpx.Response:
    dom_sem = get_domain_semaphore(url)
    h = headers or COMMON_HEADERS

    for attempt in range(max_retries + 1):
        async with GLOBAL_SEMAPHORE:
            async with dom_sem:
                try:
                    kwargs = {"headers": h, "follow_redirects": follow_redirects}
                    if timeout is not None:
                        kwargs["timeout"] = timeout
                    if method.upper() == "GET":
                        resp = await client.get(url, **kwargs)
                    elif method.upper() == "POST":
                        kwargs["json"] = json_body
                        resp = await client.post(url, **kwargs)
                    else:
                        kwargs["json"] = json_body
                        resp = await client.request(method, url, **kwargs)

                    # Retry rate-limits and transient/Cloudflare-style server errors
                    if resp.status_code in RETRY_STATUSES and attempt < max_retries:
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

async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 2,
    follow_redirects: bool = True,
    timeout: Optional[float] = None
) -> Optional[httpx.Response]:
    """GET wrapper that never raises - returns None when a request ultimately fails."""
    try:
        return await fetch_with_retry(
            client, url, method="GET", headers=headers,
            max_retries=max_retries, follow_redirects=follow_redirects, timeout=timeout
        )
    except (httpx.TimeoutException, httpx.RequestError):
        return None
    except Exception:
        return None