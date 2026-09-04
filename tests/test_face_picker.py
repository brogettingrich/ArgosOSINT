import os
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.android_bridge import is_android_environment, pending_picker_requests

client = TestClient(app)

def test_is_android_environment_helper(monkeypatch):
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    assert not is_android_environment()

    monkeypatch.setenv("ANDROID_ROOT", "/system")
    assert is_android_environment()


def test_api_face_is_native_endpoint(monkeypatch):
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    resp = client.get("/api/face/is-native")
    assert resp.status_code == 200
    assert resp.json() == {"is_native": False}

    monkeypatch.setenv("ANDROID_ROOT", "/system")
    resp = client.get("/api/face/is-native")
    assert resp.status_code == 200
    assert resp.json() == {"is_native": True}


def test_api_face_pick_native_desktop(monkeypatch):
    # On desktop/non-android, calling pick-native returns 400 not_supported
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    resp = client.post("/api/face/pick-native")
    assert resp.status_code == 400
    assert resp.json().get("status") == "not_supported"


def test_api_face_pick_native_android(monkeypatch):
    # On Android, calling pick-native queues a request
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    # Drain queue first
    while not pending_picker_requests.empty():
        pending_picker_requests.get_nowait()

    resp = client.post("/api/face/pick-native")
    assert resp.status_code == 200
    assert resp.json().get("status") == "queued"
    assert not pending_picker_requests.empty()
    item = pending_picker_requests.get_nowait()
    assert item is True
