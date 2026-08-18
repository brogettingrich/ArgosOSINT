import asyncio
import json
import logging
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ArgosAI")

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"

class AIEngine:
    @staticmethod
    async def test_connection(provider: str, api_key: str = "", model: str = "", host: str = "") -> Dict[str, Any]:
        try:
            if provider == "groq":
                if not api_key:
                    return {"success": False, "status": "no_key", "error": "No Groq API key configured"}
                headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
                payload = {
                    "model": model.strip() or DEFAULT_GROQ_MODEL,
                    "messages": [{"role": "user", "content": "Respond with 'OK'."}],
                    "max_tokens": 5
                }
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.post(GROQ_ENDPOINT, headers=headers, json=payload)
                    if resp.status_code == 200:
                        return {"success": True, "status": "online", "message": "Groq LPU Engine Online"}
                    return {"success": False, "status": "error", "error": f"Groq Error ({resp.status_code})"}

            elif provider == "ollama":
                ollama_url = (host.strip() or DEFAULT_OLLAMA_HOST).rstrip("/") + "/api/tags"
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get(ollama_url)
                    if resp.status_code == 200:
                        return {"success": True, "status": "online", "message": "Local Ollama Engine Online"}
                    return {"success": False, "status": "error", "error": f"Ollama Error ({resp.status_code})"}

            return {"success": False, "status": "error", "error": f"Unknown provider: {provider}"}
        except Exception as e:
            return {"success": False, "status": "offline", "error": str(e)}

    @staticmethod
    async def query_llm(provider: str, api_key: str, model: str, host: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Optional[str]:
        try:
            if provider == "groq":
                if not api_key:
                    return None
                headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
                payload = {
                    "model": model.strip() or DEFAULT_GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": 800
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(GROQ_ENDPOINT, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"].strip()

            elif provider == "ollama":
                ollama_url = (host.strip() or DEFAULT_OLLAMA_HOST).rstrip("/") + "/api/chat"
                payload = {
                    "model": model.strip() or DEFAULT_OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": temperature}
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(ollama_url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("message", {}).get("content", "").strip()

        except Exception as e:
            logger.warning(f"AI Query failed: {e}")
        return None

    @classmethod
    async def synthesize_permutations(cls, settings: Dict[str, Any], seed_username: str, real_names: str = "", location: str = "", keywords: str = "") -> List[str]:
        provider = settings.get("ai_provider", "groq")
        api_key = settings.get("ai_api_key", "")
        model = settings.get("ai_model", "")
        host = settings.get("ai_host", "")

        system_prompt = (
            "You are an expert OSINT pseudonym and handle intelligence generator. "
            "Analyze the target username, real name(s), location, and context clues. "
            "Identify first and last names, syllable boundaries, and common cultural naming conventions. "
            "Output ONLY a raw JSON array of 10 to 18 high-probability username permutations (lowercase, alphanumeric with dots/underscores/hyphens). "
            "Do not include explanations or markdown fences. Output ONLY the JSON array."
        )

        user_prompt = (
            f"Seed Username: {seed_username}\n"
            f"Known Names / Aliases: {real_names}\n"
            f"Location / Country: {location}\n"
            f"Context / Keywords: {keywords}\n\n"
            "Generate intelligent handle variations. Example output format: [\"handle_one\", \"handle.two\", \"handletwo_il\"]"
        )

        raw_resp = await cls.query_llm(provider, api_key, model, host, system_prompt, user_prompt, temperature=0.3)
        if not raw_resp:
            return []

        try:
            clean_json = raw_resp.strip()
            if clean_json.startswith("```"):
                clean_json = clean_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            items = json.loads(clean_json)
            if isinstance(items, list):
                return [str(x).strip().lower() for x in items if isinstance(x, str) and 2 <= len(str(x)) <= 32]
        except Exception as e:
            logger.warning(f"Failed to parse AI permutations JSON: {e} -> {raw_resp}")
        return []

    @classmethod
    async def generate_dossier_briefing(cls, settings: Dict[str, Any], target_name: str, findings: List[Dict[str, Any]], email_info: Optional[Dict[str, Any]] = None, phone_info: Optional[Dict[str, Any]] = None, location: str = "") -> Optional[str]:
        provider = settings.get("ai_provider", "groq")
        api_key = settings.get("ai_api_key", "")
        model = settings.get("ai_model", "")
        host = settings.get("ai_host", "")

        if not findings and not email_info and not phone_info:
            return None

        system_prompt = (
            "You are an expert intelligence analyst for ArgosOSINT. "
            "Write a concise, professional, 2 to 3 sentence executive intelligence briefing based on discovered accounts, "
            "identities, platforms, and locations. Be objective, concise, and highlight verified identities. "
            "Do not use markdown headers or bullet points. Output plain text only."
        )

        platforms_summary = ", ".join([f"{f.get('site')} (@{f.get('username')})" for f in findings[:15]])
        user_prompt = (
            f"Target: {target_name}\n"
            f"Location: {location or 'Unknown'}\n"
            f"Email Findings: {email_info.get('email') if email_info else 'None'}\n"
            f"Phone Findings: {phone_info.get('e164') if phone_info else 'None'} ({phone_info.get('country') if phone_info else ''})\n"
            f"Discovered Profiles ({len(findings)} Total): {platforms_summary}\n\n"
            "Provide the executive briefing."
        )

        return await cls.query_llm(provider, api_key, model, host, system_prompt, user_prompt, temperature=0.2)