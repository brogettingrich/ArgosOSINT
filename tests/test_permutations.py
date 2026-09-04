import pytest
from app.core.permutations import generate_permutations, resolve_country

def test_single_seed_username():
    perms = generate_permutations(seed_username="ozalmagor", known_names=[], location="")
    exact = [p for p in perms if p["is_seed"]]
    assert len(exact) == 1
    assert exact[0]["username"] == "ozalmagor"

def test_delimiter_swaps_and_names():
    perms = generate_permutations(seed_username="ozalmagor", known_names=["Oz Almagor"], location="")
    handles = [p["username"] for p in perms]
    assert "ozalmagor" in handles
    assert "oz_almagor" in handles or "oz.almagor" in handles
    assert "o_almagor" in handles or "oalmagor" in handles

def test_country_resolution():
    res_il = resolve_country("Israel")
    assert res_il is not None
    assert res_il["code"] == "il"
    assert res_il["name"] == "Israel"

    res_us = resolve_country("United States")
    assert res_us is not None
    assert res_us["code"] == "us"
    assert res_us["name"] == "United States"

def test_digit_collision_variants():
    # Numeric seed: user34
    perms_numeric = generate_permutations(seed_username="user34", enable_digit_collisions=True)
    numeric_handles = [p["username"] for p in perms_numeric]
    assert "user034" in numeric_handles or "user0034" in numeric_handles or "user43" in numeric_handles or "user35" in numeric_handles

    # Non-numeric seed: target
    perms_alpha = generate_permutations(seed_username="target", enable_digit_collisions=True)
    alpha_handles = [p["username"] for p in perms_alpha]
    assert "target1" in alpha_handles or "target_1" in alpha_handles or "target123" in alpha_handles