import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import DEFAULT_HOST, DEFAULT_PORT, BASE_DIR
from app.database.schema import init_db
from app.database import repository as repo
from app.core.permutations import generate_permutations
from app.core.corroboration import score_profile_corroboration
from app.core.ai_engine import AIEngine
from app.modules.username_probe import scan_usernames_async, SITES_DB
from app.modules.email_probe import probe_email_intelligence
from app.modules.phone_probe import analyze_phone_number

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ArgosOSINT")

init_db()

app = FastAPI(title="ArgosOSINT", version="2.0.0", description="Multi-Target Intelligence & AI Reasoning Reconnaissance Platform")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

class ScanRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    location: Optional[str] = None
    enable_fuzzy: bool = False
    max_permutations: int = 15

class SettingsPayload(BaseModel):
    ai_provider: str = "groq"
    ai_api_key: str = ""
    ai_model: str = "llama-3.3-70b-versatile"
    ai_host: str = "http://127.0.0.1:11434"
    enable_ai: bool = True

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "app" / "static" / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/manifest.json")
async def serve_manifest():
    manifest_file = BASE_DIR / "app" / "static" / "manifest.json"
    return FileResponse(manifest_file, media_type="application/json")

@app.get("/api/settings")
async def get_settings():
    settings = repo.get_all_settings()
    raw_key = settings.get("ai_api_key", "")
    masked_key = (raw_key[:4] + "..." + raw_key[-4:]) if len(raw_key) > 8 else raw_key
    return {
        "ai_provider": settings.get("ai_provider", "groq"),
        "ai_api_key": raw_key,
        "ai_api_key_masked": masked_key,
        "ai_model": settings.get("ai_model", "llama-3.3-70b-versatile"),
        "ai_host": settings.get("ai_host", "http://127.0.0.1:11434"),
        "enable_ai": settings.get("enable_ai", "true").lower() == "true"
    }

@app.post("/api/settings")
async def save_settings(payload: SettingsPayload):
    repo.set_setting("ai_provider", payload.ai_provider)
    if payload.ai_api_key:
        repo.set_setting("ai_api_key", payload.ai_api_key.strip())
    repo.set_setting("ai_model", payload.ai_model.strip())
    repo.set_setting("ai_host", payload.ai_host.strip())
    repo.set_setting("enable_ai", "true" if payload.enable_ai else "false")
    return {"success": True, "message": "Settings saved successfully"}

@app.get("/api/settings/health")
async def check_ai_health():
    settings = repo.get_all_settings()
    provider = settings.get("ai_provider", "groq")
    api_key = settings.get("ai_api_key", "")
    model = settings.get("ai_model", "llama-3.3-70b-versatile")
    host = settings.get("ai_host", "http://127.0.0.1:11434")
    enable_ai = settings.get("enable_ai", "true").lower() == "true"

    if not enable_ai:
        return {"online": False, "status": "disabled", "label": "AI: DISABLED", "provider": provider}

    if provider == "groq" and not api_key:
        return {"online": False, "status": "no_key", "label": "AI: OFFLINE (NO API KEY)", "provider": "groq"}

    res = await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)
    if res.get("success"):
        return {
            "online": True,
            "status": "online",
            "label": f"AI: ONLINE ({provider.upper()})",
            "provider": provider,
            "model": model
        }
    return {
        "online": False,
        "status": "unreachable",
        "label": f"AI: OFFLINE ({provider.upper()} UNREACHABLE)",
        "provider": provider,
        "error": res.get("error")
    }

@app.post("/api/settings/test")
async def test_ai_settings(payload: SettingsPayload):
    key_to_test = payload.ai_api_key or repo.get_setting("ai_api_key", "")
    res = await AIEngine.test_connection(
        provider=payload.ai_provider,
        api_key=key_to_test,
        model=payload.ai_model,
        host=payload.ai_host
    )
    return res

@app.post("/api/permutations")
async def preview_permutations(req: ScanRequest):
    if not req.username:
        return {"permutations": []}
    perms = generate_permutations(req.username, max_variations=req.max_permutations)
    return {"permutations": perms, "count": len(perms)}

@app.get("/api/dossiers")
async def list_all_dossiers():
    return repo.list_dossiers()

@app.get("/api/dossiers/{dossier_id}")
async def get_dossier(dossier_id: str):
    data = repo.get_dossier_details(dossier_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Dossier not found"})
    return data

@app.get("/api/scan/stream")
async def sse_scan_stream(
    username: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    real_name: Optional[str] = None,
    location: Optional[str] = None,
    fuzzy: bool = False,
    max_perms: int = 15
):
    target_label = username or email or phone or "Target"
    dossier_id = repo.create_dossier(
        target_name=target_label,
        seed_username=username or "",
        seed_email=email or "",
        seed_phone=phone or ""
    )

    settings = repo.get_all_settings()
    ai_enabled = settings.get("enable_ai", "true").lower() == "true" and bool(settings.get("ai_api_key") or settings.get("ai_provider") == "ollama")

    async def event_generator():
        yield f"data: {json.dumps({'type': 'init', 'dossier_id': dossier_id, 'target': target_label})}\n\n"

        email_info = None
        phone_info = None
        discovered_findings = []

        if email:
            email_info = await probe_email_intelligence(email)
            yield f"data: {json.dumps({'type': 'email_result', 'data': email_info})}\n\n"

        if phone:
            phone_info = analyze_phone_number(phone)
            yield f"data: {json.dumps({'type': 'phone_result', 'data': phone_info})}\n\n"

        if username:
            clean_seed = username.strip().lower()
            usernames_to_probe = [clean_seed]

            # 1. AI-Driven Context Permutations (if AI is enabled and connected)
            ai_perms = []
            if ai_enabled:
                yield f"data: {json.dumps({'type': 'status_update', 'message': 'AI reasoning engine analyzing context & naming structure...'})}\n\n"
                ai_perms = await AIEngine.synthesize_permutations(
                    settings=settings,
                    seed_username=clean_seed,
                    real_names=real_name or "",
                    location=location or ""
                )
                for ap in ai_perms:
                    if ap not in usernames_to_probe:
                        usernames_to_probe.append(ap)

            # 2. Local Heuristic Permutations (Always available / fallback)
            if fuzzy or not ai_perms:
                perms_list = generate_permutations(username, max_variations=max_perms)
                for p in perms_list:
                    if p["username"] not in usernames_to_probe:
                        usernames_to_probe.append(p["username"])

            yield f"data: {json.dumps({'type': 'permutation_list', 'variations': usernames_to_probe})}\n\n"

            seed_meta = {"username": clean_seed, "display_name": real_name or clean_seed}
            total_checks = len(usernames_to_probe) * len(SITES_DB)
            completed = 0

            async for result in scan_usernames_async(usernames_to_probe):
                completed += 1
                is_seed_match = (result["username"] == clean_seed)
                result["is_seed"] = is_seed_match

                if result.get("found"):
                    cand_meta = {"username": result["username"], "display_name": result["username"]}
                    corrob = score_profile_corroboration(seed_meta, cand_meta)
                    result["corroboration"] = corrob
                    repo.save_scan_result(dossier_id, result)
                    discovered_findings.append(result)

                payload = {
                    "type": "probe_result",
                    "result": result,
                    "progress": {
                        "completed": completed,
                        "total": total_checks,
                        "percent": int((completed / total_checks) * 100) if total_checks > 0 else 100
                    }
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.002)

        # 3. AI Executive Intelligence Briefing
        if ai_enabled and (discovered_findings or email_info or phone_info):
            yield f"data: {json.dumps({'type': 'status_update', 'message': 'Synthesizing executive AI intelligence briefing...'})}\n\n"
            briefing = await AIEngine.generate_dossier_briefing(
                settings=settings,
                target_name=target_label,
                findings=discovered_findings,
                email_info=email_info,
                phone_info=phone_info,
                location=location or ""
            )
            if briefing:
                yield f"data: {json.dumps({'type': 'ai_briefing', 'briefing': briefing})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'dossier_id': dossier_id})}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)