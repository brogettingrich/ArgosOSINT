import asyncio
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import DEFAULT_HOST, DEFAULT_PORT, BASE_DIR
from app.database.schema import init_db
from app.database import repository as repo
from app.core.permutations import generate_permutations
from app.core.corroboration import score_profile_corroboration
from app.modules.username_probe import scan_usernames_async, SITES_DB
from app.modules.email_probe import probe_email_intelligence
from app.modules.phone_probe import analyze_phone_number

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ArgosOSINT")

init_db()

app = FastAPI(title="ArgosOSINT", version="1.0.0", description="Multi-Target Intelligence & Reconnaissance Platform")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

class ScanRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    enable_fuzzy: bool = False
    max_permutations: int = 15
    target_name: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "app" / "static" / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/manifest.json")
async def serve_manifest():
    manifest_file = BASE_DIR / "app" / "static" / "manifest.json"
    return FileResponse(manifest_file, media_type="application/json")

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
    fuzzy: bool = False,
    max_perms: int = 12
):
    target_label = username or email or phone or "Target"
    dossier_id = repo.create_dossier(
        target_name=target_label,
        seed_username=username or "",
        seed_email=email or "",
        seed_phone=phone or ""
    )

    async def event_generator():
        yield f"data: {json.dumps({'type': 'init', 'dossier_id': dossier_id, 'target': target_label})}\n\n"

        if email:
            email_info = await probe_email_intelligence(email)
            yield f"data: {json.dumps({'type': 'email_result', 'data': email_info})}\n\n"

        if phone:
            phone_info = analyze_phone_number(phone)
            yield f"data: {json.dumps({'type': 'phone_result', 'data': phone_info})}\n\n"

        if username:
            clean_seed = username.strip().lower()
            usernames_to_probe = [clean_seed]

            if fuzzy:
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