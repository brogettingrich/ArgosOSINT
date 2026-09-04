import pytest
from app.modules.phone_probe import analyze_phone_number

def test_phone_valid_us():
    res = analyze_phone_number("+14155552671")
    assert res["valid"] is True
    assert res["e164"] == "+14155552671"
    assert "US" in res["iso"] or "1" in res["country_code"]

def test_phone_valid_il():
    res = analyze_phone_number("+972501234567")
    assert res["valid"] is True
    assert res["e164"] == "+972501234567"
    assert "IL" in res["iso"] or res["country_code"] == "972"

def test_phone_invalid_short():
    res = analyze_phone_number("123")
    assert res["valid"] is False
    assert "error" in res