import pytest
import asyncio
from app.modules.email_probe import probe_email_intelligence

@pytest.mark.asyncio
async def test_email_valid_syntax():
    res = await probe_email_intelligence("target@gmail.com")
    assert res["valid_syntax"] is True
    assert res["domain"] == "gmail.com"
    assert "deliverable" in res

@pytest.mark.asyncio
async def test_email_invalid_syntax():
    res = await probe_email_intelligence("invalid-email-address")
    assert res["valid_syntax"] is False