import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import BASE_DIR, DATABASE_PATH
from app.database.schema import init_db
from app.database import repository as repo
from app.core.permutations import generate_permutations, resolve_country
from app.core.ai_engine import AIEngine, DEFAULT_GROQ_MODEL, DEFAULT_LOCAL_HOST, DEFAULT_LOCAL_MODEL
from app.core.corroboration import score_profile_corroboration
from app.modules.username_probe import scan_usernames_async, SITES_DB
from app.modules.email_probe import probe_email_intelligence
from app.modules.phone_probe import analyze_phone_number

app = FastAPI(title="ArgosOSINT - High-Precision Intelligence Engine")

init_db()

STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.post("/api/permutations")
async def get_permutations_endpoint(payload: dict):
    username = payload.get("username", "").strip()
    known_names = payload.get("known_names", [])
    location = payload.get("location", "").strip()

    perms = generate_permutations(
        seed_username=username,
        known_names=known_names,
        location=location,
        enable_digit_collisions=False
    )
    return {"permutations": perms, "count": len(perms)}

@app.get("/api/scan/stream")
async def scan_stream_endpoint(
    username: str = "",
    known_names: str = "",
    location: str = "",
    email: str = "",
    phone: str = "",
    enable_permutations: bool = True
):
    async def event_generator():
        target_name = username or (known_names.split(',')[0].strip() if known_names else email) or "Anonymous Target"
        names_list = [n.strip() for n in known_names.split(",") if n.strip()] if known_names else []

        dossier_id = repo.create_dossier(
            target_name=target_name,
            seed_username=username,
            seed_email=email,
            seed_phone=phone
        )
        yield f"data: {json.dumps({'type': 'init', 'dossier_id': dossier_id})}\n\n"

        # 1. Email Intelligence
        email_result = None
        if email:
            email_result = await probe_email_intelligence(email)
            yield f"data: {json.dumps({'type': 'email_result', 'data': email_result})}\n\n"

        # 2. Phone Intelligence
        phone_result = None
        if phone:
            phone_result = analyze_phone_number(phone)
            yield f"data: {json.dumps({'type': 'phone_result', 'data': phone_result})}\n\n"

        # 3. Generate Permutations (Separating Exact Seed from Variations)
        perms = generate_permutations(
            seed_username=username,
            known_names=names_list,
            location=location,
            enable_digit_collisions=False
        )
        exact_seeds = [p["username"] for p in perms if p.get("is_seed")]
        secondary_perms = [p["username"] for p in perms if not p.get("is_seed")] if enable_permutations else []

        total_variants = len(exact_seeds) + len(secondary_perms)
        yield f"data: {json.dumps({'type': 'permutations_ready', 'count': total_variants})}\n\n"

        discovered_findings = []
        seed_meta = {"username": username, "display_name": names_list[0] if names_list else ""}

        country_info = resolve_country(location)
        t_country = country_info["code"] if country_info else ""
        active_cat_len = sum(1 for s in SITES_DB if not s.get("country") or (t_country and s.get("country") == t_country))
        total_probes = max(1, total_variants * active_cat_len)
        completed_probes = 0

        # PHASE 1: SCAN EXACT SEED TARGET FIRST ACROSS ALL PLATFORMS
        if exact_seeds:
            async for result in scan_usernames_async(exact_seeds, location=location, seed_name=names_list[0] if names_list else ""):
                completed_probes += 1
                if result.get("found"):
                    cand_meta = {
                        "username": result["username"],
                        "display_name": result.get("metadata", {}).get("display_name"),
                        "bio": result.get("metadata", {}).get("bio"),
                        "outbound_links": result.get("metadata", {}).get("outbound_links", [])
                    }
                    corrob = score_profile_corroboration(seed_meta, cand_meta, location=location)
                    result["corroboration"] = corrob
                    result["is_seed"] = True
                    discovered_findings.append(result)
                    repo.save_scan_result(dossier_id, result)

                pct = int((completed_probes / total_probes) * 100)
                yield f"data: {json.dumps({'type': 'probe_result', 'result': result, 'progress': {'percent': pct, 'done': completed_probes, 'total': total_probes}})}\n\n"

        # PHASE 2: SCAN SECONDARY VARIATIONS
        if secondary_perms:
            async for result in scan_usernames_async(secondary_perms, location=location, seed_name=names_list[0] if names_list else ""):
                completed_probes += 1
                if result.get("found"):
                    cand_meta = {
                        "username": result["username"],
                        "display_name": result.get("metadata", {}).get("display_name"),
                        "bio": result.get("metadata", {}).get("bio"),
                        "outbound_links": result.get("metadata", {}).get("outbound_links", [])
                    }
                    corrob = score_profile_corroboration(seed_meta, cand_meta, location=location)
                    result["corroboration"] = corrob
                    result["is_seed"] = False
                    discovered_findings.append(result)
                    repo.save_scan_result(dossier_id, result)

                pct = int((completed_probes / total_probes) * 100)
                yield f"data: {json.dumps({'type': 'probe_result', 'result': result, 'progress': {'percent': pct, 'done': completed_probes, 'total': total_probes}})}\n\n"

        # AI OSINT Executive Briefing
        settings = repo.get_all_settings()
        briefing_data = await AIEngine.generate_dossier_briefing(
            settings=settings,
            target_name=target_name,
            findings=discovered_findings,
            email_info=email_result,
            phone_info=phone_result,
            location=location
        )
        repo.update_dossier_ai_briefing(dossier_id, briefing_data)
        yield f"data: {json.dumps({'type': 'ai_briefing', 'briefing': briefing_data})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'dossier_id': dossier_id, 'found_count': len(discovered_findings)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/settings")
async def get_settings_endpoint():
    return repo.get_all_settings()

@app.post("/api/settings")
async def save_settings_endpoint(payload: dict):
    for k, v in payload.items():
        repo.set_setting(k, str(v))
    return {"status": "saved"}

@app.get("/api/settings/health")
async def get_settings_health():
    settings = repo.get_all_settings()
    enabled = settings.get("enable_ai", "true") != "false"
    provider = settings.get("ai_provider", "groq")
    api_key = settings.get("ai_api_key", "")
    model = settings.get("ai_model", DEFAULT_GROQ_MODEL)
    host = settings.get("ai_host", DEFAULT_LOCAL_HOST)

    if not enabled:
        return {"online": False, "provider": "disabled", "model": "none", "label": "AI: STANDBY (DISABLED)"}

    res = await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)
    if res.get("success"):
        model_name = model.split('/')[-1]
        return {"online": True, "provider": provider, "model": model, "label": f"AI ENGINE: ONLINE ({provider.upper()} {model_name})"}
    else:
        return {"online": False, "provider": provider, "model": model, "label": "AI ENGINE: OFFLINE (CHECK SETTINGS)"}

@app.post("/api/settings/test")
async def test_settings_connection(payload: dict):
    provider = payload.get("ai_provider") or payload.get("provider", "groq")
    api_key = payload.get("ai_api_key") or payload.get("api_key", "")
    model = payload.get("ai_model") or payload.get("model", "")
    host = payload.get("ai_host") or payload.get("host", "http://127.0.0.1:11434")
    return await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)

@app.get("/api/models/live")
async def get_live_models_endpoint(key: str = ""):
    models = await AIEngine.get_available_models(provider="groq", api_key=key)
    return {"models": models}

@app.get("/api/history")
async def get_history_endpoint():
    return repo.get_all_dossiers()