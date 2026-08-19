import os
import json
import re
import httpx
from typing import Dict, Any, List
from app.config import REQUEST_TIMEOUT, HTTP_VERIFY
from app.database import repository as repo

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_LOCAL_MODEL = "llama3.2"
DEFAULT_LOCAL_HOST = "http://127.0.0.1:11434"

GROQ_FALLBACK_MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile (Recommended - High Accuracy)"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant (Ultra-Fast)"},
    {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B (High Context)"},
    {"id": "gemma2-9b-it", "name": "Gemma 2 9B IT"}
]

LOCAL_FALLBACK_MODELS = [
    {"id": "llama3.2", "name": "Llama 3.2 (Primary)"},
    {"id": "llama3.1", "name": "Llama 3.1 (Secondary)"},
    {"id": "mistral", "name": "Mistral 7B (Fallback)"}
]

SYSTEM_PROMPT = """You are an expert OSINT analyst. Produce concise, objective executive briefings and precise machine-readable metadata. Never reveal internal chain-of-thought. Follow format rules exactly.

Instructions:
Output exactly two items: (A) a plain-text executive briefing of 2–3 sentences (no markdown, no bullets), and (B) a JSON object on a separate line (no code fences) matching the schema below. Do NOT include any explanatory text beyond these two items.
The briefing must be objective, concise, and highlight verified identities.

JSON schema:
{"briefing":string,"confidence":int (0-100),"verified_identities":string[],"inferred_identity":string,"evidence":[{"site":string,"username":string,"url":string}],"rationale":string}
"""

def resolve_api_key(key: str) -> str:
    if key and key != "__PRESERVED__":
        return key.strip()
    stored = repo.get_setting("ai_api_key", "")
    return stored.strip()

class AIEngine:
    @staticmethod
    async def get_available_models(provider: str = "groq", api_key: str = "") -> List[Dict[str, str]]:
        actual_key = resolve_api_key(api_key)
        if provider == "groq" and actual_key:
            try:
                async with httpx.AsyncClient(timeout=5.0, verify=HTTP_VERIFY) as client:
                    resp = await client.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {actual_key}"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        models = []
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if any(k in mid.lower() for k in ["llama", "mixtral", "gemma", "whisper"]):
                                models.append({"id": mid, "name": mid})
                        if models:
                            return sorted(models, key=lambda x: ("llama-3.3" not in x["id"], x["id"]))
            except Exception:
                pass
            return GROQ_FALLBACK_MODELS
        elif provider == "local":
            return LOCAL_FALLBACK_MODELS
        return GROQ_FALLBACK_MODELS

    @staticmethod
    async def test_connection(provider: str, api_key: str = "", model: str = "", host: str = DEFAULT_LOCAL_HOST) -> Dict[str, Any]:
        actual_key = resolve_api_key(api_key)
        if provider == "groq":
            if not actual_key:
                return {"success": False, "error": "Groq API key required"}
            model_to_test = model or DEFAULT_GROQ_MODEL
            try:
                async with httpx.AsyncClient(timeout=6.0, verify=HTTP_VERIFY) as client:
                    payload = {
                        "model": model_to_test,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                        "temperature": 0.1
                    }
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {actual_key}", "Content-Type": "application/json"},
                        json=payload
                    )
                    if resp.status_code == 200:
                        return {"success": True, "message": f"Groq Cloud connection verified ({model_to_test})"}
                    else:
                        err_text = resp.text[:120]
                        return {"success": False, "error": f"Groq returned HTTP {resp.status_code}: {err_text}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif provider == "local":
            target_model = model or DEFAULT_LOCAL_MODEL
            discovered_host = None
            candidate_hosts = [host, "http://127.0.0.1:11434", "http://127.0.0.1:1234", "http://127.0.0.1:8080"]
            candidate_hosts = list(dict.fromkeys(candidate_hosts))

            async with httpx.AsyncClient(timeout=4.0, verify=HTTP_VERIFY) as client:
                for h in candidate_hosts:
                    try:
                        r = await client.get(f"{h.rstrip('/')}/api/tags")
                        if r.status_code == 200:
                            discovered_host = h.rstrip('/')
                            return {"success": True, "message": f"Local Ollama online at {discovered_host} ({target_model})", "discovered_host": discovered_host}
                    except Exception:
                        pass

                    try:
                        r = await client.get(f"{h.rstrip('/')}/v1/models")
                        if r.status_code == 200:
                            discovered_host = h.rstrip('/')
                            return {"success": True, "message": f"Local LM Studio / llama.cpp online at {discovered_host} ({target_model})", "discovered_host": discovered_host}
                    except Exception:
                        pass

            return {"success": False, "error": "No local inference server reachable (Ollama: 11434, LM Studio: 1234)"}

        return {"success": False, "error": "Unknown provider"}

    @staticmethod
    async def generate_dossier_briefing(
        settings: Dict[str, str],
        target_name: str,
        findings: List[Dict[str, Any]],
        email_info: Optional[Dict[str, Any]] = None,
        phone_info: Optional[Dict[str, Any]] = None,
        location: str = ""
    ) -> Dict[str, Any]:
        enabled = settings.get("enable_ai", "true") != "false"
        if not enabled:
            return AIEngine._deterministic_fallback(target_name, findings, email_info, phone_info, location)

        provider = settings.get("ai_provider", "groq")
        api_key = resolve_api_key(settings.get("ai_api_key", ""))
        model = settings.get("ai_model", DEFAULT_GROQ_MODEL)
        host = settings.get("ai_host", DEFAULT_LOCAL_HOST)

        user_content = f"""Target: {target_name}
Location: {location or 'Unknown'}
Discovered profiles (list): {json.dumps([{'site': f['site'], 'username': f['username'], 'profile_url': f['profile_url']} for f in findings])}
Email findings: {json.dumps(email_info) if email_info else 'None'}
Phone findings: {json.dumps(phone_info) if phone_info else 'None'}
"""

        if provider == "groq" and api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0, verify=HTTP_VERIFY) as client:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 600
                    }
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=payload
                    )
                    if resp.status_code == 200:
                        raw_text = resp.json()["choices"][0]["message"]["content"]
                        parsed = AIEngine._parse_ai_output(raw_text)
                        if parsed:
                            return parsed
            except Exception:
                pass

        elif provider == "local":
            try:
                async with httpx.AsyncClient(timeout=12.0, verify=HTTP_VERIFY) as client:
                    payload = {
                        "model": model or DEFAULT_LOCAL_MODEL,
                        "prompt": f"{SYSTEM_PROMPT}\n\n{user_content}",
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                    resp = await client.post(f"{host.rstrip('/')}/api/generate", json=payload)
                    if resp.status_code == 200:
                        raw_text = resp.json().get("response", "")
                        parsed = AIEngine._parse_ai_output(raw_text)
                        if parsed:
                            return parsed
            except Exception:
                pass

        return AIEngine._deterministic_fallback(target_name, findings, email_info, phone_info, location)

    @staticmethod
    def _parse_ai_output(raw_text: str) -> Optional[Dict[str, Any]]:
        clean_text = raw_text.strip()
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

        json_match = re.search(r'(\{[\s\S]*\})', clean_text)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and "briefing" in data:
                    return data
            except Exception:
                pass

        briefing_lines = []
        for line in lines:
            if not line.startswith('{') and not line.startswith('```') and not line.startswith('JSON'):
                briefing_lines.append(line)

        briefing_text = " ".join(briefing_lines) if briefing_lines else clean_text
        if len(briefing_text) > 20:
            return {
                "briefing": briefing_text,
                "confidence": 75,
                "verified_identities": [],
                "inferred_identity": "Inferred target profile",
                "evidence": [],
                "rationale": "Automated reasoning synthesis."
            }
        return None

    @staticmethod
    def _deterministic_fallback(target_name, findings, email_info, phone_info, location):
        exact_seeds = [f for f in findings if f.get("is_seed")]
        total = len(findings)
        conf = 90 if exact_seeds else (60 if total > 0 else 30)

        verified = [f"{f['site']} (@{f['username']})" for f in exact_seeds[:3]]
        briefing = f"Target intelligence synthesis for '{target_name}'. Identified {total} public profiles across correlated networks. "
        if verified:
            briefing += f"Verified exact matches on {', '.join(verified)}. "
        if location:
            briefing += f"Regional footprint aligned with {location}. "
        briefing += "Corroboration corroborates active online presence."

        return {
            "briefing": briefing,
            "confidence": conf,
            "verified_identities": [f['username'] for f in exact_seeds[:2]],
            "inferred_identity": target_name,
            "evidence": [{'site': f['site'], 'username': f['username'], 'url': f['profile_url']} for f in exact_seeds[:4]],
            "rationale": f"Corroborated {len(exact_seeds)} seed profiles and {total - len(exact_seeds)} permutation matches."
        }