import asyncio
import json
import logging
import re
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ArgosAI")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_LOCAL_HOST = "http://127.0.0.1:11434"
DEFAULT_LOCAL_MODEL = "llama3.2"

def strip_reasoning_tags(text: str) -> str:
    if not text:
        return ""
    # Remove <think>...</think> or [REASONING]...[/REASONING] blocks
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'\[reasoning\].*?\[/reasoning\]', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'```json\s*', '', cleaned)
    cleaned = re.sub(r'```\s*', '', cleaned)
    return cleaned.strip()

class AIEngine:
    @staticmethod
    async def fetch_live_groq_models(api_key: str) -> List[Dict[str, str]]:
        clean_key = (api_key or "").strip().strip('"').strip("'")
        if not clean_key:
            return []
        try:
            headers = {"Authorization": f"Bearer {clean_key}"}
            async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
                resp = await client.get(GROQ_MODELS_URL, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models_data = data.get("data", [])
                    chat_models = []
                    for m in models_data:
                        mid = m.get("id", "")
                        # Ignore whisper, guard, or embeddings
                        if any(x in mid.lower() for x in ["whisper", "guard", "embed", "vision"]):
                            continue
                        chat_models.append({"id": mid, "name": mid})

                    # Sort prioritizing fast general chat models
                    def sort_priority(item):
                        mid = item["id"]
                        if "gpt-oss-20b" in mid: return 0
                        if "llama-3.1-8b-instant" in mid: return 1
                        if "gpt-oss-120b" in mid: return 2
                        if "llama-3.3-70b-versatile" in mid: return 3
                        if "compound-mini" in mid: return 4
                        if "allam" in mid: return 5
                        if "qwen" in mid: return 6
                        return 10

                    chat_models.sort(key=sort_priority)
                    return chat_models
        except Exception as e:
            logger.warning(f"Failed to fetch live Groq models: {e}")
        return []

    @staticmethod
    async def test_connection(provider: str, api_key: str = "", model: str = "", host: str = "") -> Dict[str, Any]:
        try:
            if provider == "groq":
                clean_key = (api_key or "").strip().strip('"').strip("'")
                if not clean_key:
                    return {"success": False, "status": "no_key", "error": "Groq API Key is required"}

                clean_model = (model or "").strip() or DEFAULT_GROQ_MODEL
                headers = {
                    "Authorization": f"Bearer {clean_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": clean_model,
                    "messages": [{"role": "user", "content": "Respond with OK"}],
                    "max_tokens": 10
                }

                async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                    resp = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
                    if resp.status_code == 200:
                        return {"success": True, "status": "online", "message": f"Groq Engine Online ({clean_model})"}
                    
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    return {"success": False, "status": "error", "error": f"Groq ({resp.status_code}): {err_msg}"}

            elif provider in ["ollama", "local"]:
                clean_host = (host or "").strip().rstrip("/") or DEFAULT_LOCAL_HOST
                # Guard against local host being ArgosOSINT port (8500)
                if ":8500" in clean_host:
                    clean_host = DEFAULT_LOCAL_HOST

                clean_model = (model or "").strip() or DEFAULT_LOCAL_MODEL

                async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
                    # 1. Test Ollama native
                    try:
                        r_ollama = await client.get(f"{clean_host}/api/tags", timeout=3.0)
                        if r_ollama.status_code == 200:
                            return {"success": True, "status": "online", "message": f"Local Ollama Online ({clean_model})"}
                    except Exception:
                        pass

                    # 2. Test Local OpenAI endpoint (LM Studio / LocalAI)
                    try:
                        r_openai = await client.get(f"{clean_host}/v1/models", timeout=3.0)
                        if r_openai.status_code in [200, 401]:
                            return {"success": True, "status": "online", "message": f"Local AI Server Online ({clean_model})"}
                    except Exception:
                        pass

                    return {
                        "success": False, 
                        "status": "offline", 
                        "error": f"Local server at {clean_host} unreachable. Make sure Ollama (port 11434) or LM Studio (port 1234) is running, or switch to Groq Cloud API."
                    }

            return {"success": False, "status": "error", "error": f"Unknown provider: {provider}"}
        except Exception as e:
            return {"success": False, "status": "offline", "error": str(e)}

    @staticmethod
    async def query_llm(provider: str, api_key: str, model: str, host: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Optional[str]:
        try:
            if provider == "groq":
                clean_key = (api_key or "").strip().strip('"').strip("'")
                if not clean_key:
                    return None

                clean_model = (model or "").strip() or DEFAULT_GROQ_MODEL
                headers = {
                    "Authorization": f"Bearer {clean_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": clean_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": 1200
                }

                async with httpx.AsyncClient(timeout=12.0, verify=False) as client:
                    resp = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        return strip_reasoning_tags(raw_content)

            elif provider in ["ollama", "local"]:
                clean_host = (host or "").strip().rstrip("/") or DEFAULT_LOCAL_HOST
                if ":8500" in clean_host:
                    clean_host = DEFAULT_LOCAL_HOST

                clean_model = (model or "").strip() or DEFAULT_LOCAL_MODEL

                async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
                    try:
                        ollama_payload = {
                            "model": clean_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "stream": False,
                            "options": {"temperature": temperature}
                        }
                        r_ollama = await client.post(f"{clean_host}/api/chat", json=ollama_payload)
                        if r_ollama.status_code == 200:
                            data = r_ollama.json()
                            raw_content = data.get("message", {}).get("content", "").strip()
                            return strip_reasoning_tags(raw_content)
                    except Exception:
                        pass

        except Exception as e:
            logger.warning(f"AI query failed: {e}")
        return None

    @classmethod
    async def synthesize_permutations(cls, settings: Dict[str, Any], seed_username: str, real_names: str = "", location: str = "", keywords: str = "") -> List[str]:
        provider = settings.get("ai_provider", "groq")
        api_key = settings.get("ai_api_key", "")
        model = settings.get("ai_model", "")
        host = settings.get("ai_host", "")

        system_prompt = (
            "You are an OSINT handle generator. "
            "Output ONLY a raw list of 15 username variations inside quotes, separated by commas. "
            "Do NOT include explanations, reasoning, or markdown fences."
        )

        user_prompt = (
            f"Username: {seed_username}\n"
            f"Known Names: {real_names}\n"
            f"Location: {location}\n\n"
            "Generate handles with first/last names, country suffixes (_il, _us, _uk), and numbers (1, 2, 3)."
        )

        raw_resp = await cls.query_llm(provider, api_key, model, host, system_prompt, user_prompt, temperature=0.3)
        if not raw_resp:
            return []

        # Extract all handles using regex to never fail on formatting
        extracted = re.findall(r'["\']?([a-zA-Z0-9._\-]{2,32})["\']?', raw_resp)
        stop_words = {"username", "usernames", "json", "list", "output", "handles", "names", "here", "are"}
        valid = [
            x.lower().strip() for x in extracted 
            if x.lower().strip() not in stop_words and len(x.strip()) >= 2
        ]
        return valid[:25]

    @classmethod
    async def generate_dossier_briefing(cls, settings: Dict[str, Any], target_name: str, findings: List[Dict[str, Any]], email_info: Optional[Dict[str, Any]] = None, phone_info: Optional[Dict[str, Any]] = None, location: str = "") -> Optional[str]:
        provider = settings.get("ai_provider", "groq")
        api_key = settings.get("ai_api_key", "")
        model = settings.get("ai_model", "")
        host = settings.get("ai_host", "")

        if not findings and not email_info and not phone_info:
            return None

        system_prompt = (
            "You are an intelligence analyst for ArgosOSINT. "
            "Write a concise, 2-sentence executive summary highlighting discovered accounts and identities. "
            "Do NOT show reasoning, thoughts, or bullet points. Output clean plain text only."
        )

        platforms_summary = ", ".join([f"{f.get('site')} (@{f.get('username')})" for f in findings[:15]])
        user_prompt = (
            f"Target: {target_name}\n"
            f"Location: {location or 'Unknown'}\n"
            f"Discovered Profiles ({len(findings)} Total): {platforms_summary}\n\n"
            "Provide the executive summary."
        )

        resp = await cls.query_llm(provider, api_key, model, host, system_prompt, user_prompt, temperature=0.2)
        return strip_reasoning_tags(resp) if resp else None