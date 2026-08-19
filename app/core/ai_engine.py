import asyncio
import json
import logging
import re
import html
import httpx
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_LOCAL_HOST = "http://127.0.0.1:11434"
DEFAULT_LOCAL_MODEL = "llama3.2"

LOCAL_PROBE_PORTS = [
    "http://127.0.0.1:11434",
    "http://localhost:11434",
    "http://127.0.0.1:1234",
    "http://localhost:1234",
    "http://127.0.0.1:8080",
    "http://localhost:8080"
]

def strip_reasoning_tags(text: str) -> str:
    if not text:
        return ""
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
                        if any(x in mid.lower() for x in ["whisper", "guard", "embed", "vision"]):
                            continue
                        chat_models.append({"id": mid, "name": mid})

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
        except Exception:
            pass
        return []

    @staticmethod
    async def get_available_models(provider: str = "groq", api_key: str = "", host: str = "") -> List[Dict[str, str]]:
        if provider == "groq":
            live = await AIEngine.fetch_live_groq_models(api_key)
            if live:
                return live
            return [
                {"id": "openai/gpt-oss-20b", "name": "OpenAI GPT-OSS 20B (Primary - Ultra-Fast)"},
                {"id": "openai/gpt-oss-120b", "name": "OpenAI GPT-OSS 120B (Deep Reasoning)"},
                {"id": "qwen/qwen3.6-27b", "name": "Qwen 3.6 27B"},
                {"id": "groq/compound-mini", "name": "Groq Compound Mini"}
            ]
        return [
            {"id": "llama3.2:latest", "name": "Llama 3.2 (Local Ollama)"},
            {"id": "llama3.1:latest", "name": "Llama 3.1 (Local Ollama)"},
            {"id": "mistral:latest", "name": "Mistral 7B (Local Ollama)"},
            {"id": "deepseek-r1:latest", "name": "DeepSeek R1 (Local Ollama)"},
            {"id": "local-model", "name": "Loaded Model (LM Studio / llama.cpp)"}
        ]

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
                clean_model = (model or "").strip() or DEFAULT_LOCAL_MODEL

                hosts_to_try = [clean_host] + [h for h in LOCAL_PROBE_PORTS if h != clean_host]

                async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
                    for h in hosts_to_try:
                        # 1. Test Ollama /api/tags
                        try:
                            r_ollama = await client.get(f"{h}/api/tags", timeout=2.0)
                            if r_ollama.status_code == 200:
                                return {
                                    "success": True, 
                                    "status": "online", 
                                    "discovered_host": h,
                                    "message": f"Local Ollama Online at {h} ({clean_model})"
                                }
                        except Exception:
                            pass

                        # 2. Test OpenAI-compatible /v1/models (LM Studio, llama.cpp)
                        try:
                            r_openai = await client.get(f"{h}/v1/models", timeout=2.0)
                            if r_openai.status_code in [200, 401]:
                                return {
                                    "success": True, 
                                    "status": "online", 
                                    "discovered_host": h,
                                    "message": f"Local AI Server Online at {h} ({clean_model})"
                                }
                        except Exception:
                            pass

                    return {
                        "success": False, 
                        "status": "offline", 
                        "error": f"Local server at {clean_host} unreachable. Ensure Ollama (port 11434) or LM Studio (port 1234) is running, or use Groq Cloud API."
                    }

            return {"success": False, "status": "error", "error": f"Unknown provider: {provider}"}
        except Exception as e:
            return {"success": False, "status": "offline", "error": str(e)}

    @staticmethod
    async def query_llm(provider: str, api_key: str, model: str, host: str, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Optional[str]:
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
                    "max_tokens": 1000
                }
                async with httpx.AsyncClient(timeout=14.0, verify=False) as client:
                    resp = await client.post(GROQ_CHAT_URL, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return strip_reasoning_tags(raw_content)

            elif provider in ["ollama", "local"]:
                clean_host = (host or "").strip().rstrip("/") or DEFAULT_LOCAL_HOST
                clean_model = (model or "").strip() or DEFAULT_LOCAL_MODEL

                async with httpx.AsyncClient(timeout=16.0, verify=False) as client:
                    # Try /v1/chat/completions (LM Studio, modern Ollama)
                    try:
                        payload = {
                            "model": clean_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "temperature": temperature
                        }
                        resp = await client.post(f"{clean_host}/v1/chat/completions", json=payload, timeout=14.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            return strip_reasoning_tags(raw_content)
                    except Exception:
                        pass

                    # Try Ollama native /api/generate
                    try:
                        payload = {
                            "model": clean_model,
                            "system": system_prompt,
                            "prompt": user_prompt,
                            "stream": False,
                            "options": {"temperature": temperature}
                        }
                        resp = await client.post(f"{clean_host}/api/generate", json=payload, timeout=14.0)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_content = data.get("response", "")
                            return strip_reasoning_tags(raw_content)
                    except Exception:
                        pass

        except Exception as e:
            logger.warning(f"Error querying LLM: {e}")
        return None

    @staticmethod
    async def generate_dossier_briefing(
        settings: Dict[str, Any],
        target_name: str,
        findings: List[Dict[str, Any]],
        email_info: Optional[Dict[str, Any]] = None,
        phone_info: Optional[Dict[str, Any]] = None,
        location: str = ""
    ) -> Dict[str, Any]:
        enabled = settings.get("enable_ai", "true") != "false"
        provider = settings.get("ai_provider", "groq")
        api_key = settings.get("ai_api_key", "")
        model = settings.get("ai_model", DEFAULT_GROQ_MODEL)
        host = settings.get("ai_host", DEFAULT_LOCAL_HOST)

        system_prompt = (
            "You are an expert OSINT analyst. Produce concise, objective executive briefings and precise machine-readable metadata. "
            "Never reveal internal chain-of-thought. Follow format rules exactly.\n\n"
            "Instructions:\n"
            "Output exactly two items: (A) a plain-text executive briefing of 2–3 sentences (no markdown, no bullets), and "
            "(B) a JSON object on a separate line (no code fences) matching the schema below. Do NOT include any explanatory text beyond these two items.\n"
            "The briefing must be objective, concise, and highlight any verified_identities. If none are verified, state the inferred identity and label it inferred.\n"
            'JSON schema: {"briefing":string,"confidence":int (0-100),"verified_identities":[string],"inferred_identity":string,"evidence":[{"site":string,"username":string,"url":string}],"rationale":string}'
        )

        discovered_list = []
        for f in findings[:25]:
            discovered_list.append({
                "site": f.get("site", "Unknown"),
                "username": f.get("username", ""),
                "profile_url": f.get("profile_url", "")
            })

        user_prompt = (
            f"Target: {target_name}\n"
            f"Location: {location or 'Unknown'}\n"
            f"Discovered profiles (list): {json.dumps(discovered_list)}\n"
            f"Email findings: {json.dumps(email_info) if email_info else 'None'}\n"
            f"Phone findings: {json.dumps(phone_info) if phone_info else 'None'}"
        )

        if enabled:
            raw_response = await AIEngine.query_llm(
                provider=provider,
                api_key=api_key,
                model=model,
                host=host,
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

            if raw_response:
                parsed = AIEngine.parse_structured_briefing(raw_response)
                if parsed:
                    return parsed

        # Deterministic Heuristic Fallback
        return AIEngine.generate_heuristic_briefing(target_name, findings, email_info, phone_info, location)

    @staticmethod
    def parse_structured_briefing(raw_text: str) -> Optional[Dict[str, Any]]:
        cleaned = strip_reasoning_tags(raw_text)
        json_match = re.search(r'\{.*"briefing".*\}', cleaned, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)

        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if isinstance(data, dict) and "briefing" in data:
                    return {
                        "briefing": data.get("briefing", ""),
                        "confidence": int(data.get("confidence", 70)),
                        "verified_identities": data.get("verified_identities", []),
                        "inferred_identity": data.get("inferred_identity", ""),
                        "evidence": data.get("evidence", []),
                        "rationale": data.get("rationale", "")
                    }
            except Exception:
                pass

        lines = [l.strip() for l in cleaned.split('\n') if l.strip()]
        if lines:
            return {
                "briefing": lines[0],
                "confidence": 75,
                "verified_identities": [],
                "inferred_identity": "",
                "evidence": [],
                "rationale": "Parsed from analyst intelligence briefing output."
            }
        return None

    @staticmethod
    def generate_heuristic_briefing(
        target_name: str,
        findings: List[Dict[str, Any]],
        email_info: Optional[Dict[str, Any]],
        phone_info: Optional[Dict[str, Any]],
        location: str
    ) -> Dict[str, Any]:
        count = len(findings)
        verified_handles = list(set([f["username"] for f in findings if f.get("is_seed")]))
        sites_list = [f["site"] for f in findings[:6]]
        sites_str = ", ".join(sites_list) if sites_list else "multiple networks"

        briefing = f"Target intelligence inquiry for '{target_name}' revealed {count} correlated online accounts across {sites_str}."
        if location:
            briefing += f" Regional correlation matches location context for '{location}'."
        if email_info and email_info.get("deliverable"):
            briefing += f" Direct mailbox linkage confirmed for {email_info.get('email')}."

        evidence = [{"site": f["site"], "username": f["username"], "url": f["profile_url"]} for f in findings[:6]]

        return {
            "briefing": briefing,
            "confidence": min(95, max(45, count * 8)),
            "verified_identities": verified_handles,
            "inferred_identity": target_name,
            "evidence": evidence,
            "rationale": f"Correlated {count} digital profile artifacts across target search matrix."
        }