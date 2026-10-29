import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app import config
from app.analysis.context import SEVERITY_ORDER, AnalysisContext
from app.analysis.verifier import verify_in_clause_or_document
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.llm.provider import LLMError, LLMFatalError, LLMProvider, LLMRateLimitError
from app.llm.redact import Redactor
from app.models.schemas import Clause, Finding, Redline
from app.playbooks.citations import source_links
from app.structure.segmenter import clause_label

log = logging.getLogger(__name__)

_SYSTEM = """You are a senior contract, employment and privacy-compliance analyst.
You review clauses of a {doc_name} (jurisdiction: {jurisdiction}) for a reader who is the {perspective} ({perspective_desc}).
The counterparty is the {counterparty}.

Use this playbook of clause types and market standards:
{playbook}

Task: identify terms that are risky, unusual, one-sided, vague or easy to miss FOR THE READER, compared with market practice.
Rules:
- "quote" MUST be one contiguous passage copied verbatim from the clause text (max 300 characters, no "..." abridging): the exact words that create the issue.
- Report at most 5 findings for this request: only the most material issues across all clauses below. Fewer is better than padding; do not restate benign boilerplate.
- Terms that are standard market practice for this document type and jurisdiction (e.g. ordinary confidentiality, a no-conflicting-agreements representation, routine tax-withholding language, standard background checks) are not findings unless they are worse than market.
- severity: "critical" = likely unlawful/unenforceable or could cause major financial or legal harm; "high" = clearly worse than market and could cost the reader significant money, rights or job security; "medium" = one-sided or vague but common in the market; "low" = minor point worth knowing. Most findings should be medium or low; reserve high and critical for the few terms that would matter most in a negotiation.
- A clause that protects the reader (for example a severance entitlement, a "good reason" resignation right, a notice period owed to the reader, a liability cap protecting the reader) is favorable, not a risk. Only flag its gaps if they are clearly worse than market.
- Set "favorable": true only for notable terms that clearly benefit the reader (severity "low").
- Set "hidden": true when the risk is easy to miss (buried under an unrelated heading, cross-reference to another document, vague discretion, deemed consent, defined-term trick, renewal/penalty tucked into another topic) and explain in "hidden_reason".
- "clause_type" must be one of the playbook ids above or "other".
- Write explanations in plain English for a non-lawyer, 1-2 sentences. "recommendation" is one concrete negotiation ask. "suggested_redline" is replacement contract language for high or critical findings only (otherwise empty).
- Classify every clause you receive in "clauses".

Respond with JSON only:
{{"clauses": [{{"clause_id": "C1", "clause_types": ["id"]}}],
 "findings": [{{"clause_id": "C1", "clause_type": "id", "title": "short title", "severity": "high", "quote": "...",
   "explanation": "...", "recommendation": "...", "suggested_redline": "",
   "hidden": false, "hidden_reason": "", "favorable": false, "confidence": 0.8}}]}}"""


@dataclass
class LLMRunStats:
    batches: int = 0
    failed_batches: int = 0
    proposed: int = 0
    rejected: int = 0
    reviewed_clauses: int = 0
    total_clauses: int = 0
    errors: List[str] = field(default_factory=list)
    stopped_reason: Optional[str] = None


def _playbook_digest(ctx: AnalysisContext) -> str:
    lines = []
    for spec in ctx.playbook.clauses:
        metric_bits = []
        for m in spec.metrics:
            r = m.range_for(ctx.jurisdiction)
            metric_bits.append(f"{m.label}: market {r.min}-{r.max} {m.unit}")
        extra = f" [{'; '.join(metric_bits)}]" if metric_bits else ""
        lines.append(f"- {spec.id} ({spec.label}): {spec.market_standard or spec.description}{extra}")
    return "\n".join(lines)


def _priority(clause: Clause) -> float:
    score = max(clause.type_scores.values()) if clause.type_scores else 0.0
    if re.search(r"sole discretion|indemnif|liquidated|waive|terminat|perpetual|irrevocable|penalt|forfeit|non-compete|arbitrat", clause.text, re.I):
        score += 0.5
    return score


def _batches(ctx: AnalysisContext, redactor: Redactor) -> List[List[Clause]]:
    candidates = [c for c in ctx.clauses if len(c.text.strip()) >= 40]
    ranked = sorted(candidates, key=_priority, reverse=True)
    budget = int(config.LLM_BATCH_CHARS * config.LLM_MAX_BATCHES * 0.9)
    chosen, used = [], 0
    for c in ranked:
        size = min(len(c.text), 3500) + 60
        if used + size > budget:
            continue
        chosen.append(c)
        used += size
    chosen.sort(key=lambda c: c.start)
    batches: List[List[Clause]] = []
    current: List[Clause] = []
    size = 0
    for c in chosen:
        clen = min(len(c.text), 3500) + 60
        if current and size + clen > config.LLM_BATCH_CHARS:
            batches.append(current)
            current, size = [], 0
        current.append(c)
        size += clen
    if current:
        batches.append(current)
    return batches


def _to_finding(ctx: AnalysisContext, item: Dict, redactor: Redactor, by_id: Dict[str, Clause]) -> Optional[Finding]:
    clause = by_id.get(str(item.get("clause_id", "")).strip())
    quote = redactor.restore(str(item.get("quote") or "")).strip()
    title = str(item.get("title") or "").strip()
    if not clause or not quote or not title:
        return None
    located = verify_in_clause_or_document(quote, clause.text, clause.start, ctx.text)
    if located is None:
        return None
    q_start, q_end, _ = located
    host = ctx.clause_at(q_start) or clause
    severity = str(item.get("severity") or "medium").lower()
    if severity not in SEVERITY_ORDER or severity == "info":
        severity = "medium"
    favorable = bool(item.get("favorable"))
    clause_type = str(item.get("clause_type") or "other")
    spec = ctx.playbook.clause(clause_type)
    if spec is None and host.clause_types:
        spec = ctx.playbook.clause(host.clause_types[0])
    try:
        confidence = float(item.get("confidence", 0.75))
    except (TypeError, ValueError):
        confidence = 0.75
    redline_text = redactor.restore(str(item.get("suggested_redline") or "")).strip()
    hidden = bool(item.get("hidden")) and not favorable
    return Finding(
        id=ctx.new_id(),
        kind="info" if favorable else ("hidden" if hidden else "risk"),
        severity="info" if favorable else severity,
        title=title[:140],
        clause_type=spec.id if spec else None,
        clause_label=spec.label if spec else None,
        category=spec.category if spec else "legal_exposure",
        clause_ids=[host.id],
        quote=ctx.text[q_start:q_end],
        quote_start=q_start,
        quote_end=q_end,
        explanation=redactor.restore(str(item.get("explanation") or "")).strip(),
        recommendation=redactor.restore(str(item.get("recommendation") or "")).strip(),
        redline=Redline(original=ctx.text[q_start:q_end], suggested=redline_text) if redline_text and not favorable else None,
        hidden_reason=redactor.restore(str(item.get("hidden_reason") or "")).strip() or None if hidden else None,
        market_comparison=(spec.market_standard or None) if spec else None,
        ai_comparison=redactor.restore(str(item.get("market_comparison") or "")).strip() or None,
        references=source_links(spec.sources, spec.references, jurisdiction=ctx.jurisdiction) if spec else [],
        confidence=max(0.3, min(0.95, confidence)),
        sources=["llm"],
        verified=True,
        favorable=favorable,
    )


def _describe_fatal(exc: LLMFatalError, provider_name: str) -> str:
    name = provider_name.capitalize()
    if isinstance(exc, LLMRateLimitError):
        wait = exc.retry_after
        when = f" Try again in about {max(1, round(wait / 60))} min." if wait and wait >= 60 else ""
        return f"{name} rate limit reached, so the remaining clauses were checked by local rules only.{when}"
    return f"{name} AI is unavailable ({exc}); the remaining clauses were checked by local rules only."


def run_llm_reasoning(ctx: AnalysisContext, provider: LLMProvider, redactor: Redactor,
                      on_progress: Optional[Callable[[int, int], None]] = None) -> tuple:
    stats = LLMRunStats(total_clauses=len(ctx.clauses))
    counter = ctx.playbook.counterparty(ctx.perspective.id)
    system = _SYSTEM.format(
        doc_name=ctx.playbook.name,
        jurisdiction=JURISDICTION_LABELS.get(ctx.jurisdiction, ctx.jurisdiction),
        perspective=ctx.perspective.label,
        perspective_desc=ctx.perspective.description,
        counterparty=counter.label if counter else "other party",
        playbook=_playbook_digest(ctx),
    )
    batches = _batches(ctx, redactor)
    by_id = ctx.clause_by_id
    findings: List[Finding] = []
    llm_types: Dict[str, List[str]] = {}
    valid_types = {s.id for s in ctx.playbook.clauses}
    done = 0

    stop = threading.Event()

    def call(batch: List[Clause]):
        if stop.is_set():
            raise LLMFatalError("skipped after an earlier AI failure")
        body = "\n\n".join(f"[{c.id}] {clause_label(c)}\n{redactor.redact(c.text[:3500])}" for c in batch)
        try:
            return provider.chat_json(system, f"Clauses to review:\n\n{body}", max_tokens=config.LLM_MAX_OUTPUT_TOKENS)
        except LLMFatalError:
            stop.set()
            raise

    with ThreadPoolExecutor(max_workers=config.LLM_CONCURRENCY) as pool:
        futures = [(batch, pool.submit(call, batch)) for batch in batches]
        for batch, fut in futures:
            stats.batches += 1
            try:
                data = fut.result()
            except LLMError as exc:
                stats.failed_batches += 1
                stats.errors.append(str(exc)[:160])
                if isinstance(exc, LLMFatalError) and stats.stopped_reason is None:
                    stats.stopped_reason = _describe_fatal(exc, provider.name)
                log.warning("LLM batch failed: %s", exc)
                continue
            finally:
                done += 1
                if on_progress:
                    on_progress(done, len(batches))
            stats.reviewed_clauses += len(batch)
            for entry in data.get("clauses") or []:
                if isinstance(entry, dict):
                    types = [t for t in entry.get("clause_types") or [] if t in valid_types]
                    llm_types[str(entry.get("clause_id"))] = types[:2]
            for item in data.get("findings") or []:
                if not isinstance(item, dict):
                    continue
                stats.proposed += 1
                finding = _to_finding(ctx, item, redactor, by_id)
                if finding is None:
                    stats.rejected += 1
                    continue
                findings.append(finding)

    for clause in ctx.clauses:
        types = llm_types.get(clause.id)
        if types:
            merged = list(dict.fromkeys(types + clause.clause_types))[:2]
            clause.clause_types = merged
    return findings, stats
