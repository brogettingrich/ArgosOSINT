import pytest
from app.core.email_pivot import EmailPivotEngine

def test_gravatar_hash_calculation():
    email = "Test.User+Filter@Domain.COM "
    expected_hash = "2017864afeda2b08dcd143d73ca587d1"  # md5 of "test.user+filter@domain.com"
    h = EmailPivotEngine.calculate_gravatar_hash(email)
    assert h == expected_hash

@pytest.mark.asyncio
async def test_public_breaches_matching():
    email = "test@gmail.com"
    breaches = await EmailPivotEngine.get_public_breaches(email)
    assert len(breaches) > 0
    assert all("compromised_email" in b for b in breaches)

@pytest.mark.asyncio
async def test_probe_all_empty_email():
    res = await EmailPivotEngine.probe_all_email_registrations("")
    assert res == []
