import logging
from typing import List

from app.classify.doc_type import detect_doc_type
from app.classify.jurisdiction import JURISDICTION_LABELS, detect_jurisdiction
from app.classify.parties import extract_parties
from app.llm.provider import LLMError, get_provider
from app.llm.redact import Redactor
from app.models.schemas import Detection, DocTypeCandidate, Party, Perspective
from app.playbooks.loader import get_playbook, load_playbooks

log = logging.getLogger(__name__)

_CONFIRM_SYSTEM = """You classify legal and policy documents. Respond with a JSON object only:
{"doc_type": one of the allowed ids, "jurisdiction": one of IN|US|EU|UK|SG|GLOBAL,
 "parties": [{"name": str, "role": str}], "reason": short string}
Choose the single best doc_type. Use "generic_contract" only if nothing else fits.
Jurisdiction is the governing law or, if absent, the country the document is clearly written for."""


def _llm_confirm(text: str, candidates: List[DocTypeCandidate]):
    provider = get_provider()
    if provider is None:
        return None
    books = load_playbooks()
    allowed = "\n".join(f"- {b.id}: {b.name} - {b.description}" for b in books.values())
    redactor = Redactor()
    excerpt = redactor.redact(text[:5000])
    user = (
        f"Allowed doc types:\n{allowed}\n\nLocal classifier ranking: "
        + ", ".join(f"{c.id} ({c.score})" for c in candidates)
        + f"\n\nDocument excerpt:\n\"\"\"\n{excerpt}\n\"\"\""
    )
    try:
        data = provider.chat_json(_CONFIRM_SYSTEM, user, max_tokens=500)
    except LLMError as exc:
        log.warning("LLM confirmation failed: %s", exc)
        return None
    if data.get("doc_type") not in books:
        return None
    parties = []
    for p in data.get("parties") or []:
        if isinstance(p, dict) and p.get("name"):
            parties.append(Party(name=redactor.restore(str(p["name"]))[:100], role=str(p.get("role") or "")[:60] or None))
    jurisdiction = data.get("jurisdiction") if data.get("jurisdiction") in JURISDICTION_LABELS else None
    return data["doc_type"], jurisdiction, parties


def detect(text: str, use_llm: bool = True) -> Detection:
    doc_type, confidence, candidates = detect_doc_type(text)
    jurisdiction, evidence = detect_jurisdiction(text)
    method = "embeddings+keywords"

    confirmed = _llm_confirm(text, candidates) if use_llm else None
    llm_parties: List[Party] = []
    if confirmed:
        llm_type, llm_jur, llm_parties = confirmed
        method = "embeddings+keywords+llm"
        if llm_type == doc_type:
            confidence = min(0.99, confidence + 0.1)
        else:
            doc_type, confidence = llm_type, 0.8
        if llm_jur and (jurisdiction == "GLOBAL" or not evidence):
            jurisdiction = llm_jur

    playbook = get_playbook(doc_type)
    parties = extract_parties(text, playbook)
    if llm_parties and len(llm_parties) >= len(parties):
        parties = llm_parties[:6]

    if all(c.id != doc_type for c in candidates):
        candidates.insert(0, DocTypeCandidate(id=doc_type, label=playbook.name, score=confidence))

    return Detection(
        doc_type=doc_type,
        doc_type_label=playbook.name,
        doc_type_confidence=round(confidence, 2),
        candidates=candidates,
        jurisdiction=jurisdiction,
        jurisdiction_label=JURISDICTION_LABELS.get(jurisdiction, jurisdiction),
        jurisdiction_evidence=evidence,
        parties=parties,
        perspectives=[Perspective(id=p.id, label=p.label, description=p.description) for p in playbook.perspectives],
        default_perspective=playbook.default_perspective,
        method=method,
    )
