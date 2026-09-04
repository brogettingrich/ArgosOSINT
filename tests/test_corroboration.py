import pytest
from app.core.corroboration import score_profile_corroboration

def test_corroboration_exact_match():
    seed = {"username": "oz_almagor", "display_name": "Oz Almagor"}
    cand = {"username": "oz_almagor", "display_name": "Oz Almagor", "bio": "Student from Israel"}
    res = score_profile_corroboration(seed, cand, location="Israel")
    assert res["score"] >= 80
    assert "CONFIRMED" in res["verdict"] or "VERIFIED" in res["verdict"] or "HIGH" in res["verdict"]

def test_corroboration_low_match():
    seed = {"username": "oz_almagor", "display_name": "Oz Almagor"}
    cand = {"username": "totally_unrelated_handle", "display_name": "Jane Doe", "bio": ""}
    res = score_profile_corroboration(seed, cand)
    assert res["score"] < 60