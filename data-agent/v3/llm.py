# -*- coding: utf-8 -*-
"""Provider-agnostic LLM wrapper — supports Gemini, OpenAI, Anthropic via REST."""

from __future__ import annotations

import os
import json
import urllib.request
import urllib.error

# ── Model Registry ───────────────────────────────────────────────────────────

MODEL_REGISTRY = {
    "gemini": {
        "default": "gemini-2.0-flash",
        "models": {
            "gemini-1.5-flash": {
                "name": "Gemini 1.5 Flash",
                "endpoint_model": "models/gemini-1.5-flash"
            },
            "gemini-2.0-flash": {
                "name": "Gemini 2.0 Flash",
                "endpoint_model": "models/gemini-2.0-flash"
            },
            "gemini-1.5-pro": {
                "name": "Gemini 1.5 Pro",
                "endpoint_model": "models/gemini-1.5-pro"
            }
        }
    },
    "openai": {
        "default": "gpt-4o-mini",
        "models": {
            "gpt-4o-mini": {
                "name": "GPT-4o-mini",
                "endpoint_model": "gpt-4o-mini"
            },
            "gpt-4o": {
                "name": "GPT-4o",
                "endpoint_model": "gpt-4o"
            }
        }
    },
    "anthropic": {
        "default": "claude-3-5-sonnet-20241022",
        "models": {
            "claude-3-5-sonnet-20241022": {
                "name": "Claude 3.5 Sonnet",
                "endpoint_model": "claude-3-5-sonnet-20241022"
            }
        }
    },
    "nvidia": {
        "default": "meta/llama-3.1-8b-instruct",
        "models": {
            "meta/llama-3.1-8b-instruct": {
                "name": "Llama 3.1 8B Instruct",
                "endpoint_model": "meta/llama-3.1-8b-instruct"
            },
            "meta/llama-3.1-70b-instruct": {
                "name": "Llama 3.1 70B Instruct",
                "endpoint_model": "meta/llama-3.1-70b-instruct"
            },
            "meta/llama-3.1-405b-instruct": {
                "name": "Llama 3.1 405B Instruct",
                "endpoint_model": "meta/llama-3.1-405b-instruct"
            },
            "nvidia/llama-3.1-nemotron-51b-instruct": {
                "name": "Llama 3.1 Nemotron 51B Instruct",
                "endpoint_model": "nvidia/llama-3.1-nemotron-51b-instruct"
            }
        }
    }
}

SUPPORTED_PROVIDERS = ["gemini", "openai", "anthropic", "nvidia"]


def detect_provider() -> tuple[str, str] | tuple[None, None]:
    """Return (provider_name, api_key) from environment, .env, or config.json, or (None, None)."""
    # 1. Load from .env if it exists in the CWD
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and v:
                        os.environ[k] = v
        except Exception:
            pass

    # 2. Check environment variables
    for env, name in [
        ("GEMINI_API_KEY",    "gemini"),
        ("OPENAI_API_KEY",    "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("NVIDIA_API_KEY",    "nvidia"),
    ]:
        key = os.environ.get(env, "").strip()
        if key:
            return name, key

    # 3. Check config.json in CWD
    config_path = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for env, name in [
                ("GEMINI_API_KEY",    "gemini"),
                ("OPENAI_API_KEY",    "openai"),
                ("ANTHROPIC_API_KEY", "anthropic"),
                ("NVIDIA_API_KEY",    "nvidia"),
            ]:
                key = cfg.get(env, "").strip()
                if key:
                    return name, key
        except Exception:
            pass

    return None, None


def get_api_key_for_provider(provider: str) -> str | None:
    """Load API key specifically for a given provider."""
    key_map = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
    }
    var_name = key_map.get(provider)
    if not var_name:
        return None

    val = os.environ.get(var_name, "").strip()
    if val:
        return val

    # Load from .env
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k == var_name and v:
                        os.environ[k] = v
                        return v
        except Exception:
            pass

    # Load from config.json
    config_path = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            val = cfg.get(var_name, "").strip()
            if val:
                return val
        except Exception:
            pass

    return None


def is_key_configured(provider: str) -> bool:
    """Return True if the API key for the provider is configured."""
    return get_api_key_for_provider(provider) is not None


def filter_useful_gemini(models_from_api: list[dict]) -> list[dict]:
    useful = []
    seen = set()
    for m in models_from_api:
        name = m.get("name", "")
        # Only include models that support generateContent
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
            
        key = name.replace("models/", "") if name.startswith("models/") else name
        key_lower = key.lower()
        
        # Only include Gemini models
        if "gemini" not in key_lower:
            continue
            
        # Exclude specialized, non-general-chat models
        excludes = [
            "embed", "tuning", "aqa", "embedding", "classifier", "toxicity",
            "robotics", "computer-use", "tts", "image", "nano", "banana",
            "experimental", "vision-preview"
        ]
        if any(ex in key_lower for ex in excludes):
            continue
            
        if key in seen:
            continue
        seen.add(key)
        
        displayName = m.get("displayName", key)
        useful.append({
            "key": key,
            "name": displayName,
            "endpoint_model": name
        })
    return useful


def filter_useful_openai(models_from_api: list[dict]) -> list[dict]:
    useful = []
    seen = set()
    for m in models_from_api:
        m_id = m.get("id", "")
        m_id_lower = m_id.lower()
        
        # Only keep gpt or o-series models
        if not (m_id_lower.startswith("gpt-") or m_id_lower.startswith("o1") or m_id_lower.startswith("o3")):
            continue
            
        # Exclude legacy/specialized/development versions
        excludes = [
            "realtime", "audio", "whisper", "dall-e", "embedding", "moderation", 
            "edit", "search", "instruct", "vision", "system", 
            "0314", "0613", "1106", "0125", "0825"
        ]
        if any(ex in m_id_lower for ex in excludes):
            continue
            
        if m_id in seen:
            continue
        seen.add(m_id)
        
        # Prettify name
        name = m_id
        if m_id == "gpt-4o-mini":
            name = "GPT-4o-mini"
        elif m_id == "gpt-4o":
            name = "GPT-4o"
        elif m_id == "o3-mini":
            name = "o3-mini"
        elif m_id == "o1-mini":
            name = "o1-mini"
        elif m_id == "o1-preview":
            name = "o1-preview"
            
        useful.append({
            "key": m_id,
            "name": name,
            "endpoint_model": m_id
        })
    # Sort
    order = ["gpt-4o-mini", "gpt-4o", "o3-mini", "o1-mini", "o1-preview"]
    useful.sort(key=lambda x: order.index(x["key"]) if x["key"] in order else 99)
    return useful


def filter_useful_anthropic(models_from_api: list[dict]) -> list[dict]:
    useful = []
    seen = set()
    for m in models_from_api:
        m_id = m.get("id", "")
        m_id_lower = m_id.lower()
        if "claude" not in m_id_lower:
            continue
        # Keep modern Claude 3, 3.5, and 3.6 chat models
        if not ("claude-3" in m_id_lower or "claude-3-5" in m_id_lower or "claude-3-6" in m_id_lower):
            continue
        # Filter out internal/specialized variants
        excludes = ["search", "input", "output", "realtime"]
        if any(ex in m_id_lower for ex in excludes):
            continue
        if m_id in seen:
            continue
        seen.add(m_id)
        useful.append({
            "key": m_id,
            "name": m.get("display_name", m_id),
            "endpoint_model": m_id
        })
    return useful


def get_verified_nvidia_models(api_key: str, models_list: list[dict]) -> list[dict]:
    import hashlib
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Hash API key to identify the cache securely
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    # Cache file path
    cache_dir = "sessions"
    cache_path = os.path.join(cache_dir, "nvidia_models_cache.json")
    
    # Try loading cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            if cache_data.get("api_key_hash") == key_hash:
                verified_ids = set(cache_data.get("working_models", []))
                if verified_ids:
                    return [m for m in models_list if m.get("id") in verified_ids]
        except Exception:
            pass
            
    # If cache miss, verify chat-eligible models concurrently
    print("\n🔍 Verifying NVIDIA model access for your API key (first-time setup)...")
    
    def is_chat_model(m_id: str) -> bool:
        m_id_lower = m_id.lower()
        excludes = [
            "embed", "embedding", "rerank", "kosmos", "sdxl", "neva", "stable-diffusion",
            "reward", "safety", "guard", "translate", "pii", "parse", "detector", "calibration", "clip", "vila"
        ]
        if any(ex in m_id_lower for ex in excludes):
            return False
            
        includes = [
            "instruct", "chat", "-it", "large", "glm", "kimi", "minimax", "step",
            "deepseek", "palmyra", "medium", "small", "yi-", "dracarys"
        ]
        if any(inc in m_id_lower for inc in includes):
            return True
        return False

    chat_models = [m.get("id") for m in models_list if m.get("id") and is_chat_model(m.get("id"))]
    working_ids = []
    
    def test_single_model(model_name: str) -> tuple[str, bool]:
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=2.0) as response:
                return model_name, True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return model_name, False
            return model_name, True
        except Exception:
            return model_name, False

    # Run up to 25 threads in parallel for speed
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(test_single_model, m): m for m in chat_models}
        for future in as_completed(futures):
            model_name, success = future.result()
            if success:
                working_ids.append(model_name)
                
    working_ids.sort()
    
    if working_ids:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key_hash": key_hash,
                    "working_models": working_ids
                }, f, indent=2)
            print(f"✓ Found {len(working_ids)} working models. Cache saved.")
        except Exception:
            pass
        
        verified_set = set(working_ids)
        return [m for m in models_list if m.get("id") in verified_set]
    else:
        print("⚠️ No working models found during verification. Falling back to all returned models.")
        return models_list


def filter_useful_nvidia(models_from_api: list[dict], api_key: str | None = None) -> list[dict]:
    if api_key:
        models_from_api = get_verified_nvidia_models(api_key, models_from_api)

    useful = []
    seen = set()

    def is_chat_model(m_id: str) -> bool:
        m_id_lower = m_id.lower()
        excludes = [
            "embed", "embedding", "rerank", "kosmos", "sdxl", "neva", "stable-diffusion",
            "reward", "safety", "guard", "translate", "pii", "parse", "detector", "calibration", "clip", "vila"
        ]
        if any(ex in m_id_lower for ex in excludes):
            return False
            
        includes = [
            "instruct", "chat", "-it", "large", "glm", "kimi", "minimax", "step",
            "deepseek", "palmyra", "medium", "small", "yi-", "dracarys"
        ]
        if any(inc in m_id_lower for inc in includes):
            return True
        return False

    for m in models_from_api:
        m_id = m.get("id", "")
        if not is_chat_model(m_id):
            continue
            
        if m_id in seen:
            continue
        seen.add(m_id)
        
        # Prettify name: "meta/llama-3.1-8b-instruct" -> "Llama 3.1 8B Instruct (meta/llama-3.1-8b-instruct)"
        parts = m_id.split("/")
        disp_name = parts[-1].replace("-", " ").title() if parts else m_id
        
        useful.append({
            "key": m_id,
            "name": f"{disp_name} ({m_id})",
            "endpoint_model": m_id
        })
    return useful


def fetch_available_models(provider: str, api_key: str | None = None) -> dict[str, dict]:
    """Dynamically fetch all useful models for a provider, or fall back to static list."""
    if not api_key:
        api_key = get_api_key_for_provider(provider)

    if not api_key:
        return MODEL_REGISTRY.get(provider, {}).get("models", {})

    if provider == "gemini":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            models_list = data.get("models", [])
            useful = filter_useful_gemini(models_list)
            if useful:
                return {m["key"]: {"name": m["name"], "endpoint_model": m["endpoint_model"]} for m in useful}
        except Exception:
            pass

    elif provider == "openai":
        try:
            url = "https://api.openai.com/v1/models"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            models_list = data.get("data", [])
            useful = filter_useful_openai(models_list)
            if useful:
                return {m["key"]: {"name": m["name"], "endpoint_model": m["endpoint_model"]} for m in useful}
        except Exception:
            pass

    elif provider == "anthropic":
        try:
            url = "https://api.anthropic.com/v1/models"
            req = urllib.request.Request(url, headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            models_list = data.get("data", [])
            useful = filter_useful_anthropic(models_list)
            if useful:
                return {m["key"]: {"name": m["name"], "endpoint_model": m["endpoint_model"]} for m in useful}
        except Exception:
            pass

    elif provider == "nvidia":
        try:
            url = "https://integrate.api.nvidia.com/v1/models"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            models_list = data.get("data", [])
            useful = filter_useful_nvidia(models_list, api_key)
            if useful:
                return {m["key"]: {"name": m["name"], "endpoint_model": m["endpoint_model"]} for m in useful}
        except Exception:
            pass

    # Default fallback to MODEL_REGISTRY
    return MODEL_REGISTRY.get(provider, {}).get("models", {})


def resolve_endpoint_model(provider: str, model_id: str, api_key: str | None = None) -> str:
    """Find the endpoint model name for a given model ID."""
    models = fetch_available_models(provider, api_key)
    if model_id in models:
        return models[model_id]["endpoint_model"]
    # Fallback to formatting rule or static default
    if provider == "gemini":
        return model_id if model_id.startswith("models/") else f"models/{model_id}"
    if provider == "nvidia":
        # Hard check to prevent base/non-chat models from being queried
        m_id_lower = model_id.lower()
        excludes = [
            "embed", "embedding", "rerank", "kosmos", "sdxl", "neva", "stable-diffusion",
            "reward", "safety", "guard", "translate", "pii", "parse", "detector", "calibration", "clip", "vila"
        ]
        includes = [
            "instruct", "chat", "-it", "large", "glm", "kimi", "minimax", "step",
            "deepseek", "palmyra", "medium", "small", "yi-", "dracarys"
        ]
        is_valid = True
        if any(ex in m_id_lower for ex in excludes):
            is_valid = False
        elif not any(inc in m_id_lower for inc in includes):
            is_valid = False
        if not is_valid:
            default_model = MODEL_REGISTRY["nvidia"]["default"]
            if model_id != default_model:
                print(f"⚠️ Warning: Model '{model_id}' is not chat-compatible; falling back to default '{default_model}'.")
            return default_model
    return model_id


def get_model_label(provider: str | None, model_id: str | None = None) -> str:
    """Human-readable model name for the startup screen."""
    if not provider:
        return "none (no API key)"
    
    m_id = model_id or MODEL_REGISTRY.get(provider, {}).get("default")
    
    # Try looking in static registry first to avoid making a network call on startup
    prov_data = MODEL_REGISTRY.get(provider)
    if prov_data and m_id in prov_data["models"]:
        return prov_data["models"][m_id]["name"]

    # If not in static registry, fetch (which might do network call)
    api_key = get_api_key_for_provider(provider)
    models = fetch_available_models(provider, api_key)
    if m_id in models:
        return models[m_id]["name"]
        
    if prov_data:
        model_info = prov_data["models"].get(m_id)
        if model_info:
            return f"{model_info['name']}"
    return f"{m_id}"


# ── Unified call ─────────────────────────────────────────────────────────────

def call_llm(
    system_prompt: str,
    user_message: str,
    conversation_history: list[dict],
    provider: str | None = None,
    api_key: str | None = None,
    model_id: str | None = None,
    timeout: int = 45,
) -> str:
    """Send a request to the configured LLM and return the text response.

    *conversation_history* is a list of {"role": "user"|"assistant", "content": str}.
    """
    if provider is None or api_key is None:
        provider, api_key = detect_provider()
    if not provider or not api_key:
        raise RuntimeError("No LLM API key configured.")

    dispatch = {
        "gemini":    _call_gemini,
        "openai":    _call_openai,
        "anthropic": _call_anthropic,
        "nvidia":    _call_nvidia,
    }
    fn = dispatch.get(provider)
    if fn is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    prov_data = MODEL_REGISTRY.get(provider)
    actual_model_id = model_id or (prov_data.get("default") if prov_data else None)

    return fn(system_prompt, user_message, conversation_history, api_key, actual_model_id, timeout)


# ── Gemini ───────────────────────────────────────────────────────────────────

def _call_gemini(system: str, user_msg: str, history: list[dict],
                 key: str, model_id: str | None, timeout: int) -> str:
    prov_data = MODEL_REGISTRY["gemini"]
    m_id = model_id or prov_data["default"]
    endpoint_model = resolve_endpoint_model("gemini", m_id, key)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"{endpoint_model}:generateContent?key={key}"
    )
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_msg}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 1024
        }
    }
    return _post_json(url, payload, timeout,
                      extract=lambda r: r["candidates"][0]["content"]["parts"][0]["text"])


# ── OpenAI ───────────────────────────────────────────────────────────────────

def _call_openai(system: str, user_msg: str, history: list[dict],
                 key: str, model_id: str | None, timeout: int) -> str:
    prov_data = MODEL_REGISTRY["openai"]
    m_id = model_id or prov_data["default"]
    endpoint_model = resolve_endpoint_model("openai", m_id, key)

    url = "https://api.openai.com/v1/chat/completions"
    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_msg})

    payload = {"model": endpoint_model, "messages": messages, "max_tokens": 1024}
    headers = {"Authorization": f"Bearer {key}"}
    return _post_json(url, payload, timeout,
                      extract=lambda r: r["choices"][0]["message"]["content"],
                      extra_headers=headers)


# ── Anthropic ────────────────────────────────────────────────────────────────

def _call_anthropic(system: str, user_msg: str, history: list[dict],
                    key: str, model_id: str | None, timeout: int) -> str:
    prov_data = MODEL_REGISTRY["anthropic"]
    m_id = model_id or prov_data["default"]
    endpoint_model = resolve_endpoint_model("anthropic", m_id, key)

    url = "https://api.anthropic.com/v1/messages"
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_msg})

    payload = {
        "model": endpoint_model,
        "max_tokens": 1024,
        "system": [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        "messages": messages,
    }
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "prompt-caching-2024-07-31",
    }
    return _post_json(url, payload, timeout,
                      extract=lambda r: r["content"][0]["text"],
                      extra_headers=headers)


# ── Nvidia NIM ───────────────────────────────────────────────────────────────

def _call_nvidia(system: str, user_msg: str, history: list[dict],
                 key: str, model_id: str | None, timeout: int) -> str:
    prov_data = MODEL_REGISTRY["nvidia"]
    m_id = model_id or prov_data["default"]
    endpoint_model = resolve_endpoint_model("nvidia", m_id, key)

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_msg})

    payload = {"model": endpoint_model, "messages": messages, "max_tokens": 1024}
    headers = {"Authorization": f"Bearer {key}"}
    return _post_json(url, payload, timeout,
                      extract=lambda r: r["choices"][0]["message"]["content"],
                      extra_headers=headers)


# ── HTTP helper ──────────────────────────────────────────────────────────────

def _post_json(url, payload, timeout, *, extract, extra_headers=None) -> str:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return extract(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API HTTP {e.code}: {err_body}") from e
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {e}") from e


def verify_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Test ping the provider's API to verify if the API key is active.
    Returns (success, error_message).
    """
    import urllib.request
    import urllib.error
    import json

    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
            return True, ""
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)

            # Handle specific HTTP status codes with user-friendly messages
            if e.code == 401:
                return False, "Invalid API Key (HTTP 401): The provided Gemini API key is invalid or unauthorized. Please check your `.env` file or environment variables."
            elif e.code == 403:
                return False, "Access Forbidden (HTTP 403): The request was forbidden by Google's AI service. Please check your API key permissions."
            elif e.code == 404:
                return False, "Not Found (HTTP 404): The requested resource was not found. This may be a temporary issue with Google's API."
            elif e.code == 429:
                return False, "Quota Exceeded (HTTP 429): You have exceeded your current quota for the Gemini API. Please check your plan and billing details."
            else:
                return False, f"HTTP {e.code} Error: Unable to complete the request to Google's AI service."
        except urllib.error.URLError as e:
            return False, "Connection Error: Failed to reach Google's AI servers. Please verify your internet connection."
        except Exception as e:
            return False, "Unable to verify your API key. Please check your internet connection and try again."

    elif provider == "openai":
        url = "https://api.openai.com/v1/models"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
            return True, ""
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)

            # Handle specific HTTP status codes with user-friendly messages
            if e.code == 401:
                return False, "Invalid API Key (HTTP 401): The provided OpenAI API key is invalid or unauthorized. Please check your `.env` file or environment variables."
            elif e.code == 403:
                return False, "Access Forbidden (HTTP 403): The request was forbidden by OpenAI. Please check your API key permissions."
            elif e.code == 404:
                return False, "Not Found (HTTP 404): The requested resource was not found. This may be a temporary issue with OpenAI's API."
            elif e.code == 429:
                return False, "Quota Exceeded (HTTP 429): You have exceeded your current quota for the OpenAI API. Please check your plan and billing details."
            else:
                return False, f"HTTP {e.code} Error: Unable to complete the request to OpenAI's service."
        except urllib.error.URLError as e:
            return False, "Connection Error: Failed to reach OpenAI's servers. Please verify your internet connection."
        except Exception as e:
            return False, "Unable to verify your API key. Please check your internet connection and try again."

    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/models"
        req = urllib.request.Request(url, headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        })
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
            return True, ""
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)

            # Handle specific HTTP status codes with user-friendly messages
            if e.code == 401:
                return False, "Invalid API Key (HTTP 401): The provided Anthropic API key is invalid or unauthorized. Please check your `.env` file or environment variables."
            elif e.code == 403:
                return False, "Access Forbidden (HTTP 403): The request was forbidden by Anthropic. Please check your API key permissions."
            elif e.code == 404:
                return False, "Not Found (HTTP 404): The requested resource was not found. This may be a temporary issue with Anthropic's API."
            elif e.code == 429:
                return False, "Quota Exceeded (HTTP 429): You have exceeded your current quota for the Anthropic API. Please check your plan and billing details."
            else:
                return False, f"HTTP {e.code} Error: Unable to complete the request to Anthropic's service."
        except urllib.error.URLError as e:
            return False, "Connection Error: Failed to reach Anthropic's servers. Please verify your internet connection."
        except Exception as e:
            return False, "Unable to verify your API key. Please check your internet connection and try again."

    elif provider == "nvidia":
        url = "https://integrate.api.nvidia.com/v1/models"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
            return True, ""
        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode("utf-8"))
                msg = err_data.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)

            # Handle specific HTTP status codes with user-friendly messages
            if e.code == 401:
                return False, "Invalid API Key (HTTP 401): The provided NVIDIA API key is invalid or unauthorized. Please check your `.env` file or environment variables."
            elif e.code == 403:
                return False, "Access Forbidden (HTTP 403): The request was forbidden by NVIDIA. Please check your API key permissions."
            elif e.code == 404:
                return False, "Not Found (HTTP 404): The requested resource was not found. This may be a temporary issue with NVIDIA's API."
            elif e.code == 429:
                return False, "Quota Exceeded (HTTP 429): You have exceeded your current quota for the NVIDIA API. Please check your plan and billing details."
            else:
                return False, f"HTTP {e.code} Error: Unable to complete the request to NVIDIA's service."
        except urllib.error.URLError as e:
            return False, "Connection Error: Failed to reach NVIDIA's servers. Please verify your internet connection."
        except Exception as e:
            return False, "Unable to verify your API key. Please check your internet connection and try again."

    return False, "Unknown provider: The specified AI provider is not supported."

