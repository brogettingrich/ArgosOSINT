import pytest
import asyncio
from app.core.http_client import create_async_client
from app.modules.username_probe import check_single_site
from app.modules.sites_catalog import SITES_CATALOG

@pytest.mark.asyncio
async def test_hackernews_real_vs_fake():
    hn_site = next(s for s in SITES_CATALOG if s["name"] == "HackerNews")
    async with create_async_client() as client:
        r_real = await check_single_site(client, hn_site, "dang")
        assert r_real["found"] is True
        assert r_real["metadata"]["display_name"] == "dang"

        r_fake = await check_single_site(client, hn_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_github_real_vs_fake():
    gh_site = next(s for s in SITES_CATALOG if s["name"] == "GitHub")
    async with create_async_client() as client:
        r_real = await check_single_site(client, gh_site, "torvalds")
        assert r_real["found"] is True
        assert "Linus" in r_real["metadata"]["display_name"]

        r_fake = await check_single_site(client, gh_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_tiktok_real_vs_fake():
    tt_site = next(s for s in SITES_CATALOG if s["name"] == "TikTok")
    async with create_async_client() as client:
        r_fake = await check_single_site(client, tt_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_spotify_fake_rejection():
    sp_site = next(s for s in SITES_CATALOG if s["name"] == "Spotify")
    async with create_async_client() as client:
        r_fake = await check_single_site(client, sp_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_twitch_fake_rejection():
    tw_site = next(s for s in SITES_CATALOG if s["name"] == "Twitch")
    async with create_async_client() as client:
        r_fake = await check_single_site(client, tw_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_wattpad_fake_rejection():
    wp_site = next(s for s in SITES_CATALOG if s["name"] == "Wattpad")
    async with create_async_client() as client:
        r_fake = await check_single_site(client, wp_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False

@pytest.mark.asyncio
async def test_vero_fake_rejection():
    v_site = next(s for s in SITES_CATALOG if s["name"] == "Vero")
    async with create_async_client() as client:
        r_fake = await check_single_site(client, v_site, "non_existent_fake_handle_881923")
        assert r_fake["found"] is False