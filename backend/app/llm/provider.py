import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import requests

from app import config

log = logging.getLogger(__name__)

# name -> (endpoint, default model, default fallback models)
_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b",
             ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.5-flash", []),
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", []),
}

_THINK = re.compile(r"<think>.*?</think>", re.S)


class LLMError(RuntimeError):
    pass


class LLMFatalError(LLMError):
    """Retrying further calls in the same analysis will not help (bad key, quota exhausted)."""


class LLMRateLimitError(LLMFatalError):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


MAX_RETRY_WAIT_SECONDS = 45.0
_RATE_HEADERS = ("limit-requests", "limit-tokens", "remaining-requests", "remaining-tokens",
                 "reset-requests", "reset-tokens")


def _parse_wait(value: Optional[str]) -> Optional[float]:
    """Seconds from a retry-after or x-ratelimit-reset value such as '7.66s', '2m59.56s' or '120'."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    parts = re.findall(r"([\d.]+)(ms|h|m|s)", value)
    if not parts:
        return None
    scale = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return sum(float(n) * scale[u] for n, u in parts)


# Per-model cooldowns shared by all calls in this process: each model has its own rate-limit bucket,
# so a rate-limited model is rested while the next model in the rotation takes the request.
_cooldowns: Dict[str, float] = {}
_cooldown_lock = threading.Lock()
_unavailable: Set[str] = set()
_UNAVAILABLE_SECONDS = 6 * 3600.0
# Smallest max_tokens a model has refused as "Request too large" (its per-minute output cap is below it).
_too_small: Dict[str, int] = {}


def _cool(key: str, seconds: float) -> None:
    with _cooldown_lock:
        _cooldowns[key] = max(_cooldowns.get(key, 0.0), time.monotonic() + seconds)


def _ready_in(key: str) -> float:
    with _cooldown_lock:
        return max(0.0, _cooldowns.get(key, 0.0) - time.monotonic())


@dataclass
class LLMProvider:
    name: str
    model: str
    url: str
    api_key: str
    fallback_models: List[str] = field(default_factory=list)
    last_rate_limits: Optional[Dict[str, str]] = None
    models_used: Set[str] = field(default_factory=set)

    @property
    def models(self) -> List[str]:
        return [self.model] + [m for m in self.fallback_models if m != self.model]

    def _pick_model(self, max_tokens: int) -> str:
        usable = [m for m in self.models if f"{self.name}:{m}" not in _unavailable
                  and max_tokens < _too_small.get(f"{self.name}:{m}", max_tokens + 1)]
        if not usable:
            raise LLMFatalError(f"no usable {self.name} model ({', '.join(self.models)}) for this request; set LLM_MODEL")
        waits = [(_ready_in(f"{self.name}:{m}"), m) for m in usable]
        ready = next((m for w, m in waits if w == 0), None)
        if ready:
            return ready
        wait, model = min(waits, key=lambda wm: wm[0])
        if wait > MAX_RETRY_WAIT_SECONDS:
            raise LLMRateLimitError(f"{self.name} rate limit reached on {', '.join(self.models)}", retry_after=wait)
        time.sleep(wait)
        return model

    def _post(self, messages: List[Dict[str, str]], max_tokens: int, temperature: float, json_mode: bool) -> str:
        payload: Dict[str, Any] = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_error = "unknown error"
        network_failures = 0
        for attempt in range(8):
            model = self._pick_model(max_tokens)
            payload["model"] = model
            if model.startswith("openai/gpt-oss") and config.LLM_REASONING_EFFORT:
                payload["reasoning_effort"] = config.LLM_REASONING_EFFORT
            else:
                payload.pop("reasoning_effort", None)
            key = f"{self.name}:{model}"
            try:
                resp = requests.post(self.url, json=payload, headers=headers, timeout=config.LLM_TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                if network_failures:
                    raise LLMFatalError(f"cannot reach {self.name}: {type(exc).__name__}") from exc
                network_failures += 1
                time.sleep(1.5)
                continue
            limits = {k: resp.headers[f"x-ratelimit-{k}"] for k in _RATE_HEADERS if f"x-ratelimit-{k}" in resp.headers}
            if limits:
                self.last_rate_limits = {"model": model, **limits}
            if resp.status_code == 200:
                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError, TypeError) as exc:
                    raise LLMError(f"unexpected response shape: {str(data)[:200]}") from exc
                self.models_used.add(model)
                return content
            last_error = f"HTTP {resp.status_code} from {model}: {resp.text[:300]}"
            if resp.status_code == 429 and "request too large" in resp.text.lower():
                with _cooldown_lock:
                    _too_small[key] = min(_too_small.get(key, max_tokens), max_tokens)
                continue
            if resp.status_code == 429:
                wait = _parse_wait(resp.headers.get("retry-after"))
                _cool(key, wait if wait is not None else 2.0 * (attempt + 1))
                continue
            if resp.status_code in (401, 403):
                raise LLMFatalError(f"{self.name} rejected the API key (HTTP {resp.status_code})")
            if resp.status_code == 404 or "decommissioned" in resp.text or "model_not_found" in resp.text:
                log.warning("LLM model %s unavailable: %s", model, resp.text[:200])
                _unavailable.add(key)
                _cool(key, _UNAVAILABLE_SECONDS)
                continue
            if resp.status_code in (500, 502, 503, 504):
                time.sleep(2.0 * min(attempt + 1, 3))
                continue
            if (resp.status_code == 400 and "response_format" in payload
                    and ("response_format" in resp.text or "json_validate_failed" in resp.text)):
                payload.pop("response_format", None)
                continue
            break
        raise LLMError(last_error)

    def chat_json(self, system: str, user: str, max_tokens: int = 4096, temperature: float = 0.1) -> Dict[str, Any]:
        content = self._post(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens, temperature, json_mode=True,
        )
        return parse_json_object(content)

    def chat_text(self, messages: List[Dict[str, str]], max_tokens: int = 1200, temperature: float = 0.2) -> str:
        return _THINK.sub("", self._post(messages, max_tokens, temperature, json_mode=False)).strip()


def parse_json_object(content: str) -> Dict[str, Any]:
    text = _THINK.sub("", content).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("model did not return JSON")
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"invalid JSON from model: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMError("model returned JSON that is not an object")
    return value


def get_provider() -> Optional[LLMProvider]:
    keys = {"groq": config.GROQ_API_KEY, "gemini": config.GEMINI_API_KEY, "openai": config.OPENAI_API_KEY}
    name = config.LLM_PROVIDER
    if name == "none":
        return None
    if not name:
        name = next((n for n in ("groq", "gemini", "openai") if keys[n]), "")
    if not name or name not in _PROVIDERS or not keys.get(name):
        return None
    url, default_model, default_fallbacks = _PROVIDERS[name]
    fallbacks = config.LLM_FALLBACK_MODELS if config.LLM_FALLBACK_MODELS is not None else default_fallbacks
    return LLMProvider(name=name, model=config.LLM_MODEL or default_model, url=url, api_key=keys[name],
                       fallback_models=list(fallbacks))


def provider_status() -> Dict[str, Any]:
    provider = get_provider()
    if provider is None:
        return {"enabled": False, "provider": None, "model": None,
                "hint": "Set GROQ_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY to enable hybrid LLM analysis."}
    cooling = {m: round(w) for m in provider.models if (w := _ready_in(f"{provider.name}:{m}")) > 0}
    return {"enabled": True, "provider": provider.name, "model": provider.model,
            "fallback_models": provider.fallback_models, "cooling_down_seconds": cooling}
