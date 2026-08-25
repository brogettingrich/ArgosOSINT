import asyncio
import json
import re
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.staticfiles import StaticFiles
from starlette.requests import Request

from app.config import BASE_DIR, DATABASE_PATH
from app.database.schema import init_db
from app.database import repository as repo
from app.core.permutations import generate_permutations, resolve_country
from app.core.ai_engine import AIEngine, DEFAULT_GROQ_MODEL, DEFAULT_LOCAL_HOST, DEFAULT_LOCAL_MODEL
from app.core.corroboration import score_profile_corroboration
from app.core.email_pivot import EmailPivotEngine
from app.modules.username_probe import scan_usernames_async, SITES_DB
from app.modules.email_probe import probe_email_intelligence
from app.modules.phone_probe import analyze_phone_number

# Initialize SQLite database
init_db()

STATIC_DIR = BASE_DIR / "app" / "static"

def parse_usernames_list(raw_input: str) -> list:
    if not raw_input:
        return []
    # Support comma, space, semicolon, tab, and newline delimiters
    tokens = re.split(r'[,;\s\n\t]+', raw_input.strip())
    cleaned = []
    for t in tokens:
        c = t.strip().lstrip('@').rstrip('/').lower()
        if c and c not in cleaned:
            cleaned.append(c)
    return cleaned

async def read_root(request: Request):
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

async def get_permutations_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    raw_user = payload.get("username", "").strip()
    known_names = payload.get("known_names", [])
    location = payload.get("location", "").strip()
    enable_digit_collisions = payload.get("enable_digit_collisions", False)

    seed_list = parse_usernames_list(raw_user)
    all_perms = []
    
    if seed_list:
        for u in seed_list:
            p = generate_permutations(seed_username=u, known_names=known_names, location=location, enable_digit_collisions=enable_digit_collisions)
            all_perms.extend(p)
    else:
        all_perms = generate_permutations(seed_username="", known_names=known_names, location=location, enable_digit_collisions=enable_digit_collisions)

    # Deduplicate permutations
    seen = set()
    deduped = []
    for item in all_perms:
        u_name = item["username"]
        if u_name not in seen:
            seen.add(u_name)
            deduped.append(item)

    return JSONResponse({"permutations": deduped, "count": len(deduped)})

async def scan_stream_endpoint(request: Request):
    params = request.query_params
    username = params.get("username", "")
    known_names = params.get("known_names", "")
    location = params.get("location", "")
    email = params.get("email", "")
    phone = params.get("phone", "")
    enable_permutations = params.get("enable_permutations", "true").lower() == "true"
    enable_digit_collisions = params.get("enable_digit_collisions", "false").lower() == "true"

    async def event_generator():
        seed_users = parse_usernames_list(username)
        names_list = [n.strip() for n in known_names.split(",") if n.strip()] if known_names else []
        
        target_name = (", ".join(seed_users) if seed_users else (names_list[0] if names_list else email)) or "Anonymous Target"

        dossier_id = repo.create_dossier(
            target_name=target_name,
            seed_username=", ".join(seed_users),
            seed_email=email,
            seed_phone=phone
        )
        yield f"data: {json.dumps({'type': 'init', 'dossier_id': dossier_id})}\n\n"

        discovered_findings = []

        # 1. Email Intelligence & Deep Account Pivots
        email_result = None
        if email:
            email_result = await probe_email_intelligence(email)
            yield f"data: {json.dumps({'type': 'email_result', 'data': email_result})}\n\n"

            # Holehe-style account registration probing & real-time breach intelligence
            email_pivots = await EmailPivotEngine.probe_all_email_registrations(email)
            breach_records = await EmailPivotEngine.get_public_breaches(email)
            yield f"data: {json.dumps({'type': 'email_pivots', 'pivots': email_pivots, 'breaches': breach_records})}\n\n"

            for ep in email_pivots:
                pivot_finding = {
                    "site": ep["service"],
                    "category": ep.get("category", "Email Pivot"),
                    "username": ep["username"],
                    "profile_url": ep["profile_url"],
                    "found": True,
                    "status_code": 200,
                    "latency_ms": 95,
                    "corroboration": {"score": 95, "verdict": "EMAIL REGISTERED"},
                    "is_seed": True,
                    "is_email_pivot": True,
                    "metadata": {
                        "display_name": ep.get("display_name"),
                        "bio": ep.get("bio"),
                        "avatar_url": ep.get("avatar_url")
                    }
                }
                discovered_findings.append(pivot_finding)
                repo.save_scan_result(dossier_id, pivot_finding)

        # 2. Phone Intelligence
        phone_result = None
        if phone:
            phone_result = analyze_phone_number(phone)
            yield f"data: {json.dumps({'type': 'phone_result', 'data': phone_result})}\n\n"

        # 3. Generate Permutations for all Seed Handles
        exact_seeds = list(seed_users)
        secondary_perms = []

        if seed_users:
            for u in seed_users:
                p_list = generate_permutations(seed_username=u, known_names=names_list, location=location, enable_digit_collisions=enable_digit_collisions)
                for p in p_list:
                    if p.get("is_seed"):
                        if p["username"] not in exact_seeds:
                            exact_seeds.append(p["username"])
                    elif enable_permutations:
                        if p["username"] not in secondary_perms and p["username"] not in exact_seeds:
                            secondary_perms.append(p["username"])
        elif names_list:
            p_list = generate_permutations(seed_username="", known_names=names_list, location=location, enable_digit_collisions=enable_digit_collisions)
            for p in p_list:
                if p.get("is_seed"):
                    exact_seeds.append(p["username"])
                elif enable_permutations:
                    secondary_perms.append(p["username"])

        total_variants = len(exact_seeds) + len(secondary_perms)
        yield f"data: {json.dumps({'type': 'permutations_ready', 'count': total_variants})}\n\n"

        seed_meta = {"username": exact_seeds[0] if exact_seeds else "", "display_name": names_list[0] if names_list else ""}

        country_info = resolve_country(location)
        t_country = country_info["code"] if country_info else ""
        active_cat_len = sum(1 for s in SITES_DB if not s.get("country") or (t_country and s.get("country") == t_country))
        total_probes = max(1, total_variants * active_cat_len)
        completed_probes = 0

        # PHASE 1: SCAN ALL EXACT SEED TARGETS FIRST
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

        # PHASE 2: SCAN SECONDARY PERMUTATIONS
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

async def get_settings_endpoint(request: Request):
    raw_settings = repo.get_all_settings()
    api_key = raw_settings.get("ai_api_key", "").strip()

    return JSONResponse({
        "ai_provider": raw_settings.get("ai_provider", "groq"),
        "ai_model": raw_settings.get("ai_model", DEFAULT_GROQ_MODEL),
        "ai_host": raw_settings.get("ai_host", DEFAULT_LOCAL_HOST),
        "enable_ai": raw_settings.get("enable_ai", "true") != "false",
        "has_api_key": bool(api_key),
        "ai_api_key": api_key
    })

async def save_settings_endpoint(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    for k, v in payload.items():
        repo.set_setting(k, str(v).strip())
    return JSONResponse({"status": "saved"})

async def get_settings_health(request: Request):
    settings = repo.get_all_settings()
    enabled = settings.get("enable_ai", "true") != "false"
    provider = settings.get("ai_provider", "groq")
    api_key = settings.get("ai_api_key", "")
    model = settings.get("ai_model", DEFAULT_GROQ_MODEL)
    host = settings.get("ai_host", DEFAULT_LOCAL_HOST)

    if not enabled:
        return JSONResponse({"online": False, "provider": "disabled", "model": "none", "label": "AI: STANDBY (DISABLED)"})

    res = await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)
    if res.get("success"):
        model_name = model.split('/')[-1]
        return JSONResponse({"online": True, "provider": provider, "model": model, "label": f"AI ENGINE: ONLINE ({provider.upper()} {model_name})"})
    else:
        return JSONResponse({"online": False, "provider": provider, "model": model, "label": "AI ENGINE: OFFLINE (CHECK SETTINGS)"})

async def test_settings_connection(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    provider = payload.get("ai_provider") or payload.get("provider", "groq")
    api_key = payload.get("ai_api_key") or payload.get("api_key", "")
    model = payload.get("ai_model") or payload.get("model", "")
    host = payload.get("ai_host") or payload.get("host", "http://127.0.0.1:11434")
    res = await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)
    return JSONResponse(res)

async def get_live_models_endpoint(request: Request):
    key = request.query_params.get("key", "")
    models = await AIEngine.get_available_models(provider="groq", api_key=key)
    return JSONResponse({"models": models})

async def get_history_endpoint(request: Request):
    return JSONResponse(repo.get_all_dossiers())

async def get_dossier_details_endpoint(request: Request):
    dossier_id = request.path_params.get("dossier_id", "")
    details = repo.get_dossier_details(dossier_id)
    if details is None:
        return JSONResponse({"error": "Dossier not found"}, status_code=404)
    return JSONResponse(details)

async def open_external_url(request: Request):
    """Receives an external URL from the in-app WebView JavaScript and queues
    it for the Android native layer to open via ACTION_VIEW Intent.
    On non-Android environments this is a harmless no-op."""
    url = request.query_params.get("url", "").strip()
    if url and (url.startswith("http://") or url.startswith("https://")):
        try:
            from app.android_bridge import pending_external_urls
            pending_external_urls.put_nowait(url)
        except Exception:
            pass  # Non-Android environment — silently ignore
    return JSONResponse({"status": "ok"})

routes = [
    Route("/", endpoint=read_root, methods=["GET"]),
    Route("/api/permutations", endpoint=get_permutations_endpoint, methods=["POST"]),
    Route("/api/scan/stream", endpoint=scan_stream_endpoint, methods=["GET"]),
    Route("/api/open-external", endpoint=open_external_url, methods=["GET"]),
    Route("/api/settings", endpoint=get_settings_endpoint, methods=["GET"]),
    Route("/api/settings", endpoint=save_settings_endpoint, methods=["POST"]),
    Route("/api/settings/health", endpoint=get_settings_health, methods=["GET"]),
    Route("/api/settings/test", endpoint=test_settings_connection, methods=["POST"]),
    Route("/api/models/live", endpoint=get_live_models_endpoint, methods=["GET"]),
    Route("/api/history", endpoint=get_history_endpoint, methods=["GET"]),
    Route("/api/dossiers/{dossier_id}", endpoint=get_dossier_details_endpoint, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(debug=False, routes=routes)