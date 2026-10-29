"""Multi-user guarantees: isolation, cache copies, quotas, own keys, admin controls, account deletion, auth."""
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth, config, usage
from app.main import app
from app.storage import db

DOCS = Path(__file__).parent / "fixtures" / "documents"
DEMO_PDF = Path(__file__).parents[2] / "demo_documents" / "offer_letters" / "bark_cfo_offer_letter_2026.pdf"


def _client(email):
    return TestClient(app, headers={"Authorization": f"Bearer test-{email}"})


def _upload(c, name="legal_nda_contract.txt", data=None, mime="text/plain"):
    r = c.post("/api/documents", files={"file": (name, data or (DOCS / name).read_bytes(), mime)})
    assert r.status_code == 200, r.text
    return r.json()


def _analyze(c, doc_id):
    r = c.post("/api/analyses", json={"document_id": doc_id, "use_llm": False})
    assert r.status_code == 200, r.text
    status = r.json()
    deadline = time.time() + 60
    while status["status"] not in ("completed", "failed"):
        assert time.time() < deadline
        time.sleep(0.2)
        status = c.get(f"/api/analyses/{status['id']}/status").json()
    assert status["status"] == "completed", status
    return status


@pytest.fixture(scope="module")
def alice():
    with _client("alice.mu@example.com") as c:
        yield c


@pytest.fixture(scope="module")
def bob():
    with _client("bob.mu@example.com") as c:
        yield c


@pytest.fixture(scope="module")
def alice_work(alice):
    doc = _upload(alice)
    return doc, _analyze(alice, doc["id"])


def test_requests_without_a_token_are_rejected():
    with TestClient(app) as c:
        for method, path in [("get", "/api/analyses"), ("get", "/api/me"), ("post", "/api/documents/text"),
                             ("get", "/api/admin/kpis")]:
            assert getattr(c, method)(path).status_code == 401, path
        assert c.get("/api/analyses", headers={"Authorization": "Bearer not-a-valid-token"}).status_code == 401
        assert c.get("/api/health").status_code == 200


def test_users_cannot_see_each_others_data(alice_work, bob):
    doc, analysis = alice_work
    aid = analysis["id"]
    for path in [f"/api/documents/{doc['id']}", f"/api/documents/{doc['id']}/file", f"/api/analyses/{aid}",
                 f"/api/analyses/{aid}/status", f"/api/analyses/{aid}/events", f"/api/analyses/{aid}/report.pdf",
                 f"/api/analyses/{aid}/lab"]:
        assert bob.get(path).status_code == 404, path
    assert bob.post(f"/api/analyses/{aid}/chat", json={"question": "What is the term?", "history": []}).status_code == 404
    assert bob.post("/api/analyses", json={"document_id": doc["id"], "use_llm": False}).status_code == 404
    assert bob.delete(f"/api/analyses/{aid}").status_code == 404
    assert aid not in {a["id"] for a in bob.get("/api/analyses").json()}


def test_identical_upload_gets_a_private_copy(alice, alice_work, bob):
    doc, analysis = alice_work
    bob_doc = _upload(bob)
    assert bob_doc["id"] != doc["id"]
    r = bob.post("/api/analyses", json={"document_id": bob_doc["id"], "use_llm": False}).json()
    assert r["cached"] and r["id"] != analysis["id"] and r["document_id"] == bob_doc["id"]
    copy = bob.get(f"/api/analyses/{r['id']}").json()
    assert copy["analysis_id"] == r["id"] and copy["document_id"] == bob_doc["id"]
    assert bob.delete(f"/api/analyses/{r['id']}").status_code == 200
    assert alice.get(f"/api/analyses/{analysis['id']}").status_code == 200


class _FakeProvider:
    name, model, owned_by_user = "groq", "fake-model", False


def test_daily_ai_quota_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(usage, "get_provider", lambda: _FakeProvider())
    profile = db.upsert_profile("quota-user", "quota@example.com", None, None, "user")
    assert usage.plan_analysis(profile, wants_ai=True).counts_against_quota
    for _ in range(usage.settings().default_ai_daily_limit):
        db.record_event(profile.id, "ai_analysis")
    plan = usage.plan_analysis(profile, wants_ai=True)
    assert plan.provider is None and "today's" in plan.notice
    db.update_profile(profile.id, ai_daily_limit=10)
    assert usage.plan_analysis(db.get_profile(profile.id), wants_ai=True).provider is not None
    assert usage.plan_analysis(profile, wants_ai=False).provider is None


def test_own_key_is_encrypted_and_bypasses_the_quota(monkeypatch):
    monkeypatch.setattr(usage, "get_provider", lambda: None)
    raw = "gsk_" + "x" * 40
    enc = usage.encrypt_key(raw)
    assert raw not in enc and usage.decrypt_key(enc) == raw
    profile = db.upsert_profile("byok-user", "byok@example.com", None, None, "user")
    for _ in range(20):
        db.record_event(profile.id, "ai_analysis")
    db.update_profile(profile.id, llm_key_enc=enc, llm_key_hint=usage.key_hint(raw))
    plan = usage.plan_analysis(db.get_profile(profile.id), wants_ai=True)
    assert plan.provider is not None and plan.provider.owned_by_user and not plan.counts_against_quota
    assert plan.provider.api_key == raw and plan.provider._bucket != "groq"


def test_own_key_endpoint_validates_the_key(monkeypatch):
    from app.api import me as me_api
    from app.llm.provider import LLMFatalError

    def reject(provider):
        raise LLMFatalError("groq rejected the API key (HTTP 401)")

    with _client("keys@example.com") as c:
        assert c.put("/api/me/llm-key", json={"api_key": "sk-not-a-groq-key-1234567890"}).status_code == 400
        monkeypatch.setattr(me_api, "validate_key", reject)
        assert c.put("/api/me/llm-key", json={"api_key": "gsk_" + "y" * 40}).status_code == 400
        monkeypatch.setattr(me_api, "validate_key", lambda provider: None)
        me = c.put("/api/me/llm-key", json={"api_key": "gsk_" + "y" * 40}).json()
        assert me["has_own_key"] and me["own_key_hint"] == "gsk_...yyyy"
        stored = db.get_profile(me["id"]).llm_key_enc
        assert stored and "yyyy" not in stored
        assert not c.delete("/api/me/llm-key").json()["has_own_key"]


def test_admin_routes_need_the_admin_role(alice):
    assert alice.get("/api/admin/kpis").status_code == 403
    assert alice.get("/api/admin/users").status_code == 403
    assert alice.put("/api/admin/settings", json={"default_ai_daily_limit": 9, "chat_daily_limit": 9,
                                                  "ai_enabled": True}).status_code == 403


def test_admin_kpis_users_and_settings(alice_work):
    with _client("admin@example.com") as admin:
        me = admin.get("/api/me").json()
        assert me["role"] == "admin"
        kpis = admin.get("/api/admin/kpis").json()
        assert kpis["users_total"] >= 2 and kpis["analyses_total"] >= 1 and len(kpis["daily"]) == 30
        page = admin.get("/api/admin/users", params={"q": "alice.mu"}).json()
        assert page["total"] == 1
        body = str(kpis) + str(page)
        assert "clauses" not in body and "findings" not in body and "text" not in page["users"][0]

        alice_id = page["users"][0]["id"]
        updated = admin.patch(f"/api/admin/users/{alice_id}", json={"ai_daily_limit": 7}).json()
        assert updated["ai_daily_limit"] == 7 and updated["limit_overridden"]
        assert admin.patch(f"/api/admin/users/{me['id']}", json={"status": "blocked"}).status_code == 400

        current = admin.get("/api/admin/settings").json()
        paused = admin.put("/api/admin/settings", json={**current, "ai_enabled": False}).json()
        assert paused["ai_enabled"] is False
        plan = usage.plan_analysis(db.get_profile(alice_id), wants_ai=True)
        assert plan.provider is None and "paused" in (plan.notice or "")
        admin.put("/api/admin/settings", json=current)


def test_blocked_users_are_refused():
    with _client("blocked.user@example.com") as c:
        uid = c.get("/api/me").json()["id"]
        with _client("admin@example.com") as admin:
            assert admin.patch(f"/api/admin/users/{uid}", json={"status": "blocked"}).json()["status"] == "blocked"
            assert c.get("/api/analyses").status_code == 403
            admin.patch(f"/api/admin/users/{uid}", json={"status": "active"})
        assert c.get("/api/analyses").status_code == 200


def test_deleting_the_account_removes_everything():
    with _client("leaving@example.com") as c:
        uid = c.get("/api/me").json()["id"]
        doc = _upload(c, DEMO_PDF.name, DEMO_PDF.read_bytes(), "application/pdf")
        _analyze(c, doc["id"])
        stored = config.FILES_DIR / uid / f"{doc['id']}.pdf"
        assert stored.exists()
        assert c.get(f"/api/documents/{doc['id']}/file").content.startswith(b"%PDF")
        assert c.delete("/api/me").json() == {"deleted": True}
        assert not stored.exists()
        assert db.get_profile(uid) is None
        assert db.list_analyses(uid) == [] and db.find_document_by_hash(db.sha256(DEMO_PDF.read_bytes()), uid) is None


def _rsa_token(key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": "supa-user-1", "email": "Person@Example.com", "aud": "authenticated",
              "iss": "https://proj.supabase.co/auth/v1", "exp": now + timedelta(minutes=5),
              "user_metadata": {"full_name": "Person One", "avatar_url": "https://example.com/a.png"}}
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


def test_supabase_tokens_are_verified(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setattr(config, "AUTH_MODE", "supabase")
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(auth, "_jwks_client", lambda: FakeJwks())

    ident = auth._identity(_rsa_token(key))
    assert ident["sub"] == "supa-user-1" and ident["email"] == "person@example.com" and ident["name"] == "Person One"
    for bad in (_rsa_token(key, exp=datetime.now(timezone.utc) - timedelta(minutes=1)),
                _rsa_token(key, aud="anon"), _rsa_token(key, iss="https://evil.example.com/auth/v1"),
                _rsa_token(rsa.generate_private_key(public_exponent=65537, key_size=2048))):
        with pytest.raises(Exception) as err:
            auth._identity(bad)
        assert getattr(err.value, "status_code", None) == 401
    with pytest.raises(Exception) as err:
        auth._identity("test-person@example.com")
    assert err.value.status_code == 401


@pytest.mark.parametrize("env", [{"AUTH_MODE": "local"}, {"AUTH_MODE": "test"}, {"AUTH_MODE": "supabase"}])
def test_production_refuses_unsafe_configuration(env):
    run_env = {**os.environ, "APP_ENV": "production", "ENCRYPTION_KEY": "", **env}
    r = subprocess.run([sys.executable, "-c", "import app.config"], cwd=Path(__file__).parents[1], env=run_env,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "APP_ENV=production requires" in r.stderr
