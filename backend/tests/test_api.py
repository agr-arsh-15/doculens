"""End-to-end API flow with FastAPI's TestClient (local mode, isolated database)."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

DOCS = Path(__file__).parent / "fixtures" / "documents"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, headers={"Authorization": "Bearer test-alice@example.com"}) as c:
        yield c


def _upload(client, name, as_name=None):
    files = {"file": (as_name or name, (DOCS / name).read_bytes(), "text/plain")}
    r = client.post("/api/documents", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def _run(client, document_id, **body):
    r = client.post("/api/analyses", json={"document_id": document_id, "use_llm": False, **body})
    assert r.status_code == 200, r.text
    status = r.json()
    deadline = time.time() + 60
    while status["status"] not in ("completed", "failed") and time.time() < deadline:
        time.sleep(0.2)
        status = client.get(f"/api/analyses/{status['id']}/status").json()
    assert status["status"] == "completed", status
    return status


@pytest.fixture(scope="module")
def india(client):
    doc = _upload(client, "india_offer_letter.txt")
    return doc, _run(client, doc["id"])


@pytest.fixture(scope="module")
def us_offer(client):
    doc = _upload(client, "hr_offer_letter.txt")
    return doc, _run(client, doc["id"])


def test_benchmarks_and_findings_link_to_sources(client, india):
    result = client.get(f"/api/analyses/{india[1]['id']}").json()
    assert result["benchmarks"]
    for item in result["benchmarks"]:
        assert item["sources"] and all(s["url"].startswith("https://") for s in item["sources"])
    with_standard = [f for f in result["findings"] if f.get("market_comparison") and f["kind"] != "benchmark"]
    assert with_standard
    for f in with_standard:
        assert any(r.get("url") for r in f["references"]), f["title"]
    # Indian sources are listed before other jurisdictions' sources
    bond = next(f for f in result["findings"] if f["clause_type"] == "training_bond")
    assert bond["references"][0]["publisher"] == "Supreme Court of India"
    pdf = client.get(f"/api/analyses/{india[1]['id']}/report.pdf")
    assert pdf.status_code == 200 and b"/URI" in pdf.content


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert {"IN", "US", "EU"} <= set(meta["jurisdictions"])
    assert client.get("/api/samples").status_code == 404
    playbooks = client.get("/api/playbooks").json()
    assert {"offer_letter", "nda", "msa_saas", "tos"} <= {p["id"] for p in playbooks}


def test_upload_detects_document_and_dedupes(client):
    first = _upload(client, "india_offer_letter.txt", "offer.txt")
    second = _upload(client, "india_offer_letter.txt", "again.txt")
    assert first["id"] == second["id"]
    assert first["detection"]["doc_type"] == "offer_letter"
    assert first["detection"]["jurisdiction"] == "IN"
    detail = client.get(f"/api/documents/{first['id']}").json()
    assert detail["clauses"] and detail["text"].startswith("LETTER OF APPOINTMENT")


@pytest.mark.parametrize("name,payload,code", [
    ("empty.txt", b"", 400),
    ("legacy.doc", b"\xd0\xcf\x11\xe0 not really a word file", 415),
    ("fake.pdf", b"this is not a pdf at all but long enough to parse", 415),
    ("script.exe", b"MZ binary", 415),
])
def test_upload_rejects_bad_files(client, name, payload, code):
    r = client.post("/api/documents", files={"file": (name, payload, "application/octet-stream")})
    assert r.status_code == code


def test_paste_text_requires_some_content(client):
    assert client.post("/api/documents/text", json={"text": "too short"}).status_code == 400
    text = (DOCS / "legal_nda_contract.txt").read_text()
    doc = client.post("/api/documents/text", json={"text": text, "filename": "nda"}).json()
    assert doc["filename"] == "nda.txt" and doc["detection"]["doc_type"] == "nda"


def test_analysis_result_and_event_stream(client, india):
    doc, status = india
    result = client.get(f"/api/analyses/{status['id']}").json()
    assert result["doc_type"] == "offer_letter" and result["perspective"] == "employee"
    assert result["engine"]["mode"] == "local"
    assert result["scorecard"]["grade"] == "F"
    assert any("original" in f["title"].lower() for f in result["findings"])

    with client.stream("GET", f"/api/analyses/{status['id']}/events") as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert events[-1]["status"] == "completed"


def test_cache_hit_and_force(client, india):
    doc, status = india
    again = client.post("/api/analyses", json={"document_id": doc["id"], "use_llm": False}).json()
    assert again["cached"] and again["id"] == status["id"]
    forced = client.post("/api/analyses", json={"document_id": doc["id"], "use_llm": False, "force": True}).json()
    assert not forced["cached"] and forced["id"] != status["id"]


def test_perspective_changes_the_verdict(client, india):
    doc, status = india
    employer = _run(client, doc["id"], perspective="employer")
    a = client.get(f"/api/analyses/{status['id']}").json()["scorecard"]["overall"]
    b = client.get(f"/api/analyses/{employer['id']}").json()["scorecard"]["overall"]
    assert b > a


def test_invalid_overrides_are_rejected(client, india):
    doc, _ = india
    assert client.post("/api/analyses", json={"document_id": doc["id"], "doc_type": "lease"}).status_code == 400
    assert client.post("/api/analyses", json={"document_id": doc["id"], "jurisdiction": "XX"}).status_code == 400
    assert client.post("/api/analyses", json={"document_id": "missing"}).status_code == 404


def test_chat_cites_clauses(client, india):
    _, status = india
    r = client.post(f"/api/analyses/{status['id']}/chat", json={"question": "What happens if I resign early?"}).json()
    assert r["mode"] == "retrieval"
    assert r["citations"] and all(c["clause_id"].startswith("C") for c in r["citations"])
    assert any("notice" in c["excerpt"].lower() or "bond" in c["excerpt"].lower() for c in r["citations"])


def test_negotiation_email(client, india):
    _, status = india
    r = client.post(f"/api/analyses/{status['id']}/negotiation-email", json={"tone": "collaborative"}).json()
    assert r["subject"] and r["body"].startswith("Hi HR team")


def test_pdf_report(client, india):
    _, status = india
    r = client.get(f"/api/analyses/{status['id']}/report.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"]


def test_lab_layers(client, india):
    _, status = india
    lab = client.get(f"/api/analyses/{status['id']}/lab").json()
    assert {"layer1", "layer2", "layer3", "layer4"} <= set(lab)


def test_compare_and_history(client, india, us_offer):
    _, a = india
    _, b = us_offer
    cmp = client.post("/api/compare", json={"analysis_a": a["id"], "analysis_b": b["id"]}).json()
    assert cmp["rows"] and cmp["headline"]
    assert client.post("/api/compare", json={"analysis_a": a["id"], "analysis_b": a["id"]}).status_code == 400

    ids = {h["id"] for h in client.get("/api/analyses", params={"q": "Job Offer"}).json()}
    assert {a["id"], b["id"]} <= ids
    assert client.get("/api/analyses", params={"q": "no-such-document"}).json() == []


def test_delete(client, us_offer):
    doc, _ = us_offer
    extra = _run(client, doc["id"], perspective="employer")
    assert client.delete(f"/api/analyses/{extra['id']}").status_code == 200
    assert client.get(f"/api/analyses/{extra['id']}").status_code == 404
