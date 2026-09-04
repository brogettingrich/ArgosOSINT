import pytest
import asyncio
from app.core.http_client import create_async_client, get_random_user_agent, fetch_with_retry

def test_user_agent_rotation():
    ua1 = get_random_user_agent()
    assert "Mozilla/5.0" in ua1

@pytest.mark.asyncio
async def test_client_fetch():
    async with create_async_client() as client:
        resp = await fetch_with_retry(client, "https://api.github.com/zen")
        assert resp.status_code == 200