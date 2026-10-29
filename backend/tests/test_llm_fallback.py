"""Groq/LLM failure handling: rate limits and bad keys must degrade to local findings, never hang or crash."""
import pytest

from app import config
from app.analysis import engine
from app.llm import provider as provider_mod
from app.llm.provider import LLMFatalError, LLMProvider, LLMRateLimitError, _parse_wait
from eval.harness import analyze_sample


class FakeResponse:
    def __init__(self, status, headers=None, text=""):
        self.status_code = status
        self.headers = headers or {}
        self.text = text

    def json(self):
        return {"choices": [{"message": {"content": "{}"}}]}


def _provider(fallbacks=()):
    return LLMProvider(name="groq", model="test-model", url="https://example.invalid", api_key="test",
                       fallback_models=list(fallbacks))


@pytest.fixture(autouse=True)
def _reset_cooldowns():
    state = (provider_mod._cooldowns, provider_mod._unavailable, provider_mod._too_small)
    for s in state:
        s.clear()
    yield
    for s in state:
        s.clear()


@pytest.mark.parametrize("value,seconds", [
    ("12", 12.0), ("7.66s", 7.66), ("2m59.56s", 179.56), ("1h2m", 3720.0), ("250ms", 0.25), ("", None), ("soon", None),
])
def test_parse_wait(value, seconds):
    assert _parse_wait(value) == (pytest.approx(seconds) if seconds is not None else None)


def test_daily_limit_fails_fast_and_records_headers(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return FakeResponse(429, {"retry-after": "900", "x-ratelimit-remaining-tokens": "0",
                                  "x-ratelimit-limit-tokens": "12000"}, "tokens per day exceeded")

    monkeypatch.setattr(provider_mod.requests, "post", post)
    p = _provider()
    with pytest.raises(LLMRateLimitError) as err:
        p.chat_json("system", "user")
    assert len(calls) == 1 and err.value.retry_after == pytest.approx(900, abs=1)
    assert p.last_rate_limits == {"model": "test-model", "remaining-tokens": "0", "limit-tokens": "12000"}


def test_short_rate_limit_is_retried(monkeypatch):
    responses = [FakeResponse(429, {"retry-after": "0.01"}), FakeResponse(200)]
    monkeypatch.setattr(provider_mod.requests, "post", lambda *a, **k: responses.pop(0))
    assert _provider().chat_json("system", "user") == {}


def test_rate_limited_model_hands_off_to_fallback(monkeypatch):
    models = []

    def post(url, json, **kwargs):
        models.append(json["model"])
        return FakeResponse(429, {"retry-after": "15"}) if json["model"] == "test-model" else FakeResponse(200)

    monkeypatch.setattr(provider_mod.requests, "post", post)
    monkeypatch.setattr(provider_mod.time, "sleep", lambda s: pytest.fail("should switch models, not sleep"))
    p = _provider(["backup-model"])
    assert p.chat_json("system", "user") == {} and p.chat_json("system", "user") == {}
    assert models == ["test-model", "backup-model", "backup-model"]
    assert p.models_used == {"backup-model"}


def test_model_too_small_for_a_request_is_only_skipped_for_large_requests(monkeypatch):
    models = []

    def post(url, json, **kwargs):
        models.append((json["model"], json["max_tokens"]))
        if json["model"] == "test-model" and json["max_tokens"] > 1000:
            return FakeResponse(429, text='{"error":{"message":"Request too large for model on output tokens per minute"}}')
        return FakeResponse(200)

    monkeypatch.setattr(provider_mod.requests, "post", post)
    monkeypatch.setattr(provider_mod.time, "sleep", lambda s: pytest.fail("should switch models, not sleep"))
    p = _provider(["backup-model"])
    p.chat_json("system", "user", max_tokens=4096)
    p.chat_json("system", "user", max_tokens=4096)
    p.chat_json("system", "user", max_tokens=500)
    assert models == [("test-model", 4096), ("backup-model", 4096), ("backup-model", 4096), ("test-model", 500)]


def test_unreachable_provider_gives_up_after_one_retry(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise provider_mod.requests.ConnectionError("offline")

    monkeypatch.setattr(provider_mod.requests, "post", post)
    monkeypatch.setattr(provider_mod.time, "sleep", lambda s: None)
    with pytest.raises(LLMFatalError, match="cannot reach groq"):
        _provider().chat_json("system", "user")
    assert len(calls) == 2


def test_retired_model_is_skipped(monkeypatch):
    def post(url, json, **kwargs):
        if json["model"] == "test-model":
            return FakeResponse(404, text='{"error": {"code": "model_not_found"}}')
        return FakeResponse(200)

    monkeypatch.setattr(provider_mod.requests, "post", post)
    assert _provider(["backup-model"]).chat_json("system", "user") == {}
    with pytest.raises(LLMFatalError, match="no usable groq model"):
        _provider().chat_json("system", "user")


def test_think_tags_are_stripped():
    assert provider_mod.parse_json_object('<think>{"draft": 1}</think>{"ok": true}') == {"ok": True}


def test_bad_key_is_fatal(monkeypatch):
    monkeypatch.setattr(provider_mod.requests, "post", lambda *a, **k: FakeResponse(401, text="invalid api key"))
    with pytest.raises(LLMFatalError, match="rejected the API key"):
        _provider().chat_json("system", "user")


class RateLimitedProvider(LLMProvider):
    def __init__(self):
        super().__init__(name="groq", model="test-model", url="https://example.invalid", api_key="test")
        self.calls = 0

    def chat_json(self, *args, **kwargs):
        self.calls += 1
        raise LLMRateLimitError("groq rate limit reached", retry_after=600)


def test_rate_limited_analysis_falls_back_to_local(monkeypatch):
    fake = RateLimitedProvider()
    monkeypatch.setattr(engine, "get_provider", lambda: fake)
    monkeypatch.setattr(config, "LLM_BATCH_CHARS", 1500)
    result = analyze_sample("india_offer_letter.txt", use_llm=True).result

    assert result.engine.mode == "local"
    assert result.engine.llm_batches > 1 and result.engine.llm_failed_batches == result.engine.llm_batches
    assert fake.calls <= 2, "remaining batches must be skipped once the quota is exhausted"
    assert any("rate limit reached" in w and "10 min" in w for w in result.engine.warnings)
    assert result.summary_source.startswith("template")
    assert len(result.findings) > 5


def test_degraded_analysis_is_not_cached(monkeypatch):
    import time
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(engine, "get_provider", RateLimitedProvider)
    data = (Path(__file__).parent / "fixtures" / "documents" / "legal_nda_contract.txt").read_bytes()
    with TestClient(app) as client:
        doc = client.post("/api/documents", files={"file": ("nda.txt", data, "text/plain")}).json()
        first = client.post("/api/analyses", json={"document_id": doc["id"]}).json()
        deadline = time.time() + 60
        while client.get(f"/api/analyses/{first['id']}/status").json()["status"] != "completed":
            assert time.time() < deadline
            time.sleep(0.2)
        again = client.post("/api/analyses", json={"document_id": doc["id"]}).json()
    assert not again["cached"] and again["id"] != first["id"]
