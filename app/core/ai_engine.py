import os
import json
import re
import httpx
from typing import Dict, Any, List, Optional
from app.config import REQUEST_TIMEOUT, HTTP_VERIFY
from app.database import repository as repo

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_LOCAL_MODEL = "llama3.2"
DEFAULT_LOCAL_HOST = "http://127.0.0.1:11434"

MODEL_PRETTY_NAMES = {
    "openai/gpt-oss-20b": "GPT-OSS 20B (Recommended · High Limit & Ultra-Fast)",
    "groq/compound-mini": "Groq Compound Mini (Fast & Generous Limits)",
    "openai/gpt-oss-120b": "GPT-OSS 120B (High Intelligence Flagship)",
    "qwen/qwen3.6-27b": "Qwen 3.6 27B (Reasoning Preview)",
    "allam-2-7b": "Allam 2 7B",
    "canopylabs/orpheus-v1-english": "Orpheus v1 English",
    "llama-3.3-70b-versatile": "Llama 3.3 70B Versatile",
    "llama-3.1-8b-instant": "Llama 3.1 8B Instant"
}

GROQ_FALLBACK_MODELS = [
    {"id": "openai/gpt-oss-20b", "name": "GPT-OSS 20B (Recommended · High Limit & Ultra-Fast)"},
    {"id": "groq/compound-mini", "name": "Groq Compound Mini (Fast & Generous Limits)"},
    {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B (High Intelligence Flagship)"},
    {"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B (Reasoning Preview)"},
    {"id": "allam-2-7b", "name": "Allam 2 7B"},
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile"},
    {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant"}
]

LOCAL_FALLBACK_MODELS = [
    {"id": "llama3.2", "name": "Llama 3.2 (Primary)"},
    {"id": "llama3.1", "name": "Llama 3.1 (Secondary)"},
    {"id": "mistral", "name": "Mistral 7B (Fallback)"}
]

SYSTEM_PROMPT = """You are an OSINT Intelligence Analyst. Produce a concise, 2-3 sentence executive intelligence briefing summarizing discovered accounts, verified identities, and key takeaways.
Output ONLY a single valid JSON object. Do NOT include markdown code fences (no ```json), chain-of-thought, thinking tags (<think>), or introductory text.

JSON format:
{"briefing":"2-3 clear, objective sentences summarizing the verified findings and digital footprint.","confidence":85,"verified_identities":["username"],"inferred_identity":"Target Identifier","evidence":[{"site":"GitHub","username":"user","url":"https://..."}],"rationale":"1 sentence summarizing verification basis."}
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
                            mid_l = mid.lower()
                            # Filter out non-chat models (guard, whisper, vision-only, etc.)
                            if any(bad in mid_l for bad in ["guard", "whisper", "vision", "moderation", "safeguard"]):
                                continue
                            if any(k in mid_l for k in ["gpt-oss", "compound", "llama", "qwen", "mixtral", "gemma", "allam", "orpheus"]):
                                name = MODEL_PRETTY_NAMES.get(mid, mid)
                                models.append({"id": mid, "name": name})
                        if models:
                            # Prioritize gpt-oss-20b and compound-mini at the top
                            def _sort_key(x):
                                mid = x["id"]
                                if "gpt-oss-20b" in mid: return 0
                                if "compound-mini" in mid: return 1
                                if "gpt-oss-120b" in mid: return 2
                                if "llama" in mid: return 3
                                return 4
                            return sorted(models, key=_sort_key)
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
                async with httpx.AsyncClient(timeout=15.0, verify=HTTP_VERIFY) as client:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_content}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1500
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
                async with httpx.AsyncClient(timeout=15.0, verify=HTTP_VERIFY) as client:
                    payload = {
                        "model": model or DEFAULT_LOCAL_MODEL,
                        "prompt": f"{SYSTEM_PROMPT}\n\n{user_content}",
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 1500}
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

        # Method 1: Standard JSON parsing from all candidate blocks in raw text
        candidates = re.findall(r'(\{(?:[^{}]|(?:\{[^{}]*\}))*\})', clean_text, flags=re.S)
        for c in reversed(candidates):
            try:
                data = json.loads(c)
                if isinstance(data, dict) and "briefing" in data:
                    b = str(data["briefing"]).strip()
                    # Strip any residual thinking tags or meta headers
                    b = re.sub(r'<think>[\s\S]*?</think>', '', b, flags=re.I)
                    b = re.sub(r'<think>[\s\S]*', '', b, flags=re.I)
                    b = re.sub(r'^(?:Briefing|Summary|Analysis):\s*', '', b, flags=re.I).strip()
                    if len(b) > 15 and not b.startswith(("1.", "2.", "Output", "Schema", "2-3")):
                        data["briefing"] = b
                        return data
            except Exception:
                pass

        # Method 2: Robust regex extraction of "briefing" field from reasoning stream
        m_b = re.findall(r'"briefing"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', clean_text)
        if m_b:
            final_b = m_b[-1].replace('\\"', '"').replace('\\n', ' ').strip()
            if len(final_b) > 20 and not final_b.startswith(("2-3", "Output", "Schema")):
                m_conf = re.findall(r'"confidence"\s*:\s*(\d+)', clean_text)
                conf = int(m_conf[-1]) if m_conf else 75
                m_rat = re.findall(r'"rationale"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', clean_text)
                rat = m_rat[-1].replace('\\"', '"').strip() if m_rat else "Intelligence synthesis."
                return {
                    "briefing": final_b,
                    "confidence": conf,
                    "verified_identities": [],
                    "inferred_identity": "Inferred Target Profile",
                    "evidence": [],
                    "rationale": rat
                }

        # Method 3: Clean text fallback with all thinking tokens stripped
        stripped = re.sub(r'<think>[\s\S]*?</think>', '', clean_text, flags=re.I)
        stripped = re.sub(r'<think>[\s\S]*', '', stripped, flags=re.I).strip()
        stripped = re.sub(r'```(?:json)?[\s\S]*?```', '', stripped, flags=re.I).strip()
        stripped = re.sub(r'[\*\#\_`]', '', stripped).strip()
        stripped = re.sub(r'^(?:Here\'s a thinking process|Analysis|Reasoning|Output|Draft Briefing):\s*', '', stripped, flags=re.I).strip()

        if len(stripped) > 15:
            return {
                "briefing": stripped,
                "confidence": 75,
                "verified_identities": [],
                "inferred_identity": "Inferred Target Profile",
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
        briefing += "Findings corroborate an active online presence."

        return {
            "briefing": briefing,
            "confidence": conf,
            "verified_identities": [f['username'] for f in exact_seeds[:2]],
            "inferred_identity": target_name,
            "evidence": [{'site': f['site'], 'username': f['username'], 'url': f['profile_url']} for f in exact_seeds[:4]],
            "rationale": f"Corroborated {len(exact_seeds)} seed profiles and {total - len(exact_seeds)} permutation matches."
        }