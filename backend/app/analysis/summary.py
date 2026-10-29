import logging
from typing import List, Optional, Tuple

from app.analysis.context import AnalysisContext
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.lab.textrank import extract_textrank_summary
from app.llm.provider import LLMError, LLMProvider
from app.llm.redact import Redactor
from app.models.schemas import BenchmarkItem, Finding, Scorecard

log = logging.getLogger(__name__)

_SYSTEM = """You write executive summaries of contract risk reviews for non-lawyers.
Write 4-6 sentences of plain English, no bullet points, no markdown. Cover: what the document is and what it commits the reader to,
the overall risk verdict, the 2-3 most important issues (with why they matter), and anything hidden or missing.
Only use facts from the input. Do not give legal advice disclaimers."""


def _template_summary(ctx: AnalysisContext, findings: List[Finding], benchmarks: List[BenchmarkItem], card: Scorecard) -> str:
    jurisdiction = JURISDICTION_LABELS.get(ctx.jurisdiction, ctx.jurisdiction)
    risky = [f for f in findings if not f.favorable and f.kind != "missing"]
    hidden = [f for f in findings if f.kind == "hidden"]
    missing = [f for f in findings if f.kind == "missing"]
    favorable = [f for f in findings if f.favorable]
    parts = [
        f"This {ctx.playbook.name.lower()} ({jurisdiction}) was reviewed from the perspective of the {ctx.perspective.label.lower()}.",
        f"Overall risk is {card.risk_level} with a score of {card.overall}/100 (grade {card.grade}).",
    ]
    if risky:
        titles = list(dict.fromkeys(f.title.lower() for f in risky))[:3]
        parts.append(f"The most important issue{'s are' if len(titles) > 1 else ' is'}: {'; '.join(titles)}.")
    else:
        parts.append("No material risk terms were detected in the clauses reviewed.")
    if hidden:
        parts.append(f"{len(hidden)} risk(s) are easy to miss because of where or how they are written.")
    if missing:
        parts.append("Expected protections are missing: " + ", ".join(f.clause_label or f.title for f in missing[:3]) + ".")
    off_market = [b for b in benchmarks if b.assessment == "unfavorable"]
    if off_market:
        parts.append("Terms outside the market range: " + "; ".join(b.note.rstrip(".") for b in off_market[:2]) + ".")
    if favorable:
        parts.append(f"{len(favorable)} term(s) work in your favor.")
    return " ".join(parts)


def build_summary(ctx: AnalysisContext, findings: List[Finding], benchmarks: List[BenchmarkItem], card: Scorecard,
                  provider: Optional[LLMProvider], redactor: Redactor) -> Tuple[str, str]:
    fallback = _template_summary(ctx, findings, benchmarks, card)
    if provider is None:
        key_sentences = extract_textrank_summary([c.text for c in ctx.clauses if len(c.text) > 60], top_k=1)
        return fallback, "template+textrank" if key_sentences else "template"
    lines = [
        f"Document type: {ctx.playbook.name}; jurisdiction: {JURISDICTION_LABELS.get(ctx.jurisdiction, ctx.jurisdiction)}",
        f"Reader: {ctx.perspective.label}",
        f"Score: {card.overall}/100, grade {card.grade}, risk {card.risk_level}",
        "Findings (severity | kind | title | explanation):",
    ]
    for f in findings[:14]:
        lines.append(f"- {f.severity} | {f.kind}{' (favorable)' if f.favorable else ''} | {f.title} | {f.explanation[:220]}")
    for b in benchmarks[:6]:
        lines.append(f"- benchmark: {b.note} ({b.assessment})")
    lines.append("Opening of the document:\n" + redactor.redact(ctx.text[:1500]))
    try:
        text = provider.chat_text([{"role": "system", "content": _SYSTEM}, {"role": "user", "content": "\n".join(lines)}],
                                  max_tokens=450)
        text = redactor.restore(text).strip()
        if len(text) > 80:
            return text, f"llm:{provider.name}"
    except LLMError as exc:
        log.warning("LLM summary failed: %s", exc)
    return fallback, "template"
