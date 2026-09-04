import pytest
from app.database import repository as repo

def test_dossier_lifecycle_and_settings_masking():
    dossier_id = repo.create_dossier("Test Subject", seed_username="testuser", seed_email="test@test.com")
    assert dossier_id is not None

    repo.save_scan_result(dossier_id, {
        "site": "GitHub",
        "category": "Developer",
        "username": "testuser",
        "profile_url": "https://github.com/testuser",
        "found": True,
        "status_code": 200,
        "latency_ms": 120,
        "corroboration": {"score": 95, "verdict": "VERIFIED"},
        "metadata": {"display_name": "Test User"}
    })

    details = repo.get_dossier_details(dossier_id)
    assert details is not None
    assert details["target_name"] == "Test Subject"
    assert len(details["results"]) == 1
    assert details["results"][0]["site"] == "GitHub"

    # Settings test using isolated test key
    repo.set_setting("test_suite_internal_key", "test_value_123")
    stored = repo.get_setting("test_suite_internal_key")
    assert stored == "test_value_123"