"""Turn selected findings into a ready-to-send negotiation email."""
import logging
from typing import List

from app.llm.provider import LLMError, get_provider
from app.llm.redact import Redactor
from app.models.schemas import AnalysisResult, Finding, NegotiationEmailResponse

log = logging.getLogger(__name__)

_SYSTEM = """You write short, professional negotiation emails on behalf of the reader of a contract.
Return JSON: {"subject": str, "body": str}.
- Open warmly, state that the reader is keen to proceed, then list each requested change as a numbered point.
- For each point: name the clause, the concern in one sentence, and the specific change requested (use the suggested wording when given).
- Keep it under 250 words. Tone: {tone}. No legal threats, no claims of illegality unless the input states a statutory reference.
- Sign off with "[Your name]". Do not invent facts."""

_RECIPIENT = {
    "offer_letter": "HR team", "employment_agreement": "HR team", "msa_saas": "Account team",
    "tos": "Support team", "privacy_policy": "Privacy team", "dpa_compliance": "Privacy team",
    "nda": "there", "generic_contract": "there",
}


def _pick(result: AnalysisResult, finding_ids: List[str]) -> List[Finding]:
    by_id = {f.id: f for f in result.findings}
    chosen = [by_id[i] for i in finding_ids if i in by_id]
    if not chosen:
        chosen = [by_id[i] for i in result.scorecard.top_negotiation if i in by_id]
    return [f for f in chosen if not f.favorable][:6]


def _template(result: AnalysisResult, findings: List[Finding], recipient: str, tone: str) -> NegotiationEmailResponse:
    opener = ("Thank you for sharing the document. I'm keen to move forward and would like to clarify a few points first:"
              if tone == "collaborative" else
              "Before I can sign, the following points need to be addressed:")
    points = []
    for i, f in enumerate(findings, 1):
        where = f" ({f.clause_label})" if f.clause_label else ""
        ask = f.redline.suggested if f.redline else (f.recommendation or "Please revisit this term.")
        points.append(f"{i}. {f.title}{where}: {ask}")
    body = "\n".join([f"Hi {recipient},", "", opener, "", *points, "",
                      "Happy to discuss on a call if that's easier.", "", "Best regards,", "[Your name]"])
    return NegotiationEmailResponse(subject=f"Requested changes: {result.filename}", body=body, mode="template")


def build_negotiation_email(result: AnalysisResult, finding_ids: List[str], recipient: str | None, tone: str) -> NegotiationEmailResponse:
    findings = _pick(result, finding_ids)
    recipient = recipient or _RECIPIENT.get(result.doc_type, "the counterparty")
    if not findings:
        return NegotiationEmailResponse(subject=f"Re: {result.filename}",
                                        body="No negotiable findings were selected.", mode="template")
    provider = get_provider()
    if provider is None:
        return _template(result, findings, recipient, tone)
    redactor = Redactor(names=[p.name.split(' ("')[0] for p in result.parties])
    lines = [f"Document: {result.doc_type_label}. Reader: {result.perspective_label}. Recipient: {recipient}.", "Points:"]
    for f in findings:
        lines.append(f"- Clause: {f.clause_label or 'n/a'} | Issue: {f.title} | Why: {f.explanation[:300]}"
                     f" | Ask: {(f.redline.suggested if f.redline else f.recommendation)[:400]}"
                     + (f" | Reference: {', '.join(r.title for r in f.references[:2])}" if f.references else ""))
    try:
        data = provider.chat_json(_SYSTEM.replace("{tone}", tone), redactor.redact("\n".join(lines)), max_tokens=900, temperature=0.3)
        subject, body = str(data.get("subject") or ""), str(data.get("body") or "")
        if subject and body:
            return NegotiationEmailResponse(subject=redactor.restore(subject), body=redactor.restore(body), mode="llm")
    except LLMError as exc:
        log.warning("Negotiation email LLM call failed: %s", exc)
    return _template(result, findings, recipient, tone)
