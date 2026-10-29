import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.analysis.context import SEVERITY_ORDER, AnalysisContext
from app.analysis.values import convert_duration, find_durations, sentence_bounds
from app.models.schemas import Clause, Finding
from app.nlp.embeddings import embedder
from app.playbooks.citations import source_links
from app.structure.segmenter import clause_label

_CATCH_ALL_HEADINGS = re.compile(
    r"\b(miscellaneous|general( provisions| terms)?|other (terms|provisions)|definitions|interpretation|boilerplate|"
    r"notices|entire agreement|severability|joining|formalities|annexure|schedule|appendix|exhibit|acknowledg|welcome|introduction|"
    r"preamble|recitals|additional terms|other conditions|standard terms)\b",
    re.I,
)

_DISCRETION = re.compile(
    r"(sole\s+(and\s+absolute\s+)?discretion|absolute\s+discretion|unfettered\s+discretion|as\s+(it|they|the\s+\w+)\s+(may\s+)?deems?\s+(fit|appropriate|necessary|proper)|"
    r"at\s+(its|their|our)\s+(own\s+)?discretion|for\s+any\s+reason\s+or\s+no\s+reason)",
    re.I,
)
_EXTERNAL_REF = re.compile(
    r"(as\s+(amended|modified|updated|revised)\s+from\s+time\s+to\s+time|incorporated\s+(herein\s+)?by\s+reference|https?://[^\s)\"']+|www\.[^\s)\"']+)",
    re.I,
)
_SCHEDULE_REF = re.compile(r"\b(Schedule|Annexure|Annex|Exhibit|Appendix|Attachment)\s+([A-Z0-9]{1,3})\b")
_DEEMED = re.compile(
    r"(automatically\s+renew|auto[- ]?renew|deemed\s+(to\s+(have\s+been|be)\s+)?(accepted|renewed|agreed|consented)|"
    r"continued\s+(use|access|employment)[^.]{0,60}(constitutes?|deemed|signif)[^.]{0,20}(accept|agree|consent)|"
    r"silence[^.]{0,40}deemed)",
    re.I,
)
_SURVIVAL = re.compile(r"surviv\w*[^.]{0,160}(indefinitely|in\s+perpetuity|perpetual|without\s+limit(ation)?\s+(of|in)\s+time)", re.I)
_PENALTY = re.compile(
    r"(liquidated\s+damages|forfeit(ure)?|penalty\s+of(?!\s+perjury)|shall\s+(be\s+liable\s+to\s+)?pay[^.]{0,60}(sum|amount|penalty)|"
    r"(repay|refund|reimburse)[^.]{0,100}(if|in\s+the\s+event)[^.]{0,80}(leave|resign|terminat|cancel|exit))",
    re.I,
)
_OBLIGATION = re.compile(
    r"\b(?P<subj>you|we|the\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?|[A-Z][A-Za-z]+)\s+(?:shall|must|agrees?\s+to|undertakes?\s+to|will\s+be\s+required\s+to|is\s+required\s+to|is\s+obligated\s+to)\b"
)

_CONTRADICTION_SPECS: List[Tuple[str, str, re.Pattern, str]] = [
    ("notice", "Notice period", re.compile(r"notice\s+period|notice\s+of\s+resignation|resign", re.I), "days"),
    ("probation", "Probation period", re.compile(r"probation", re.I), "months"),
    ("payment", "Payment deadline", re.compile(r"(invoice|payment|payable)[^.]{0,40}within|within[^.]{0,30}of\s+(the\s+)?(invoice|receipt)", re.I), "days"),
    ("breach_notice", "Breach notification window", re.compile(r"(breach|incident)[^.]{0,80}notif|notif[^.]{0,80}(breach|incident)", re.I), "hours"),
    ("non_compete", "Non-compete duration", re.compile(r"non[- ]?compet|not\s+(to\s+)?compete|competing\s+business", re.I), "months"),
]


def _finding(ctx: AnalysisContext, *, title: str, severity: str, start: int, end: int, explanation: str,
             recommendation: str, hidden_reason: Optional[str], kind: str = "hidden", favorable: bool = False,
             confidence: float = 0.7, category: Optional[str] = None) -> Finding:
    quote, q_start, q_end = ctx.sentence_quote(start, end)
    clause = ctx.clause_at(q_start)
    spec = ctx.playbook.clause(clause.clause_types[0]) if clause and clause.clause_types else None
    return Finding(
        id=ctx.new_id(),
        kind="info" if favorable else kind,
        severity="info" if favorable else severity,
        title=title,
        clause_type=spec.id if spec else None,
        clause_label=spec.label if spec else None,
        category=category or (spec.category if spec else "legal_exposure"),
        clause_ids=[clause.id] if clause else [],
        quote=quote,
        quote_start=q_start,
        quote_end=q_end,
        explanation=explanation,
        recommendation="" if favorable else recommendation,
        hidden_reason=None if favorable else hidden_reason,
        confidence=confidence,
        sources=["rule"],
        verified=True,
        favorable=favorable,
    )


def _aliases(ctx: AnalysisContext) -> Tuple[List[str], List[str]]:
    user = [a.lower() for a in ctx.perspective.aliases]
    counter = ctx.playbook.counterparty(ctx.perspective.id)
    other = [a.lower() for a in counter.aliases] if counter else []
    return user, other


def _holder_is_user(ctx: AnalysisContext, window: str) -> Optional[bool]:
    user, other = _aliases(ctx)
    w = window.lower()
    def last_pos(names):
        return max((w.rfind(n) for n in names if n and re.search(rf"\b{re.escape(n)}\b", w)), default=-1)
    u, o = last_pos(user), last_pos(other)
    if u == -1 and o == -1:
        return None
    return u > o


def _payer_is_user(ctx: AnalysisContext, sentence: str) -> Optional[bool]:
    user, other = _aliases(ctx)
    m = re.search(r"\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(?:shall|will|must|agrees?\s+to|is\s+liable\s+to|shall\s+be\s+liable\s+to)\s+"
                  r"(?:pay|repay|refund|reimburse|forfeit|be\s+liable)", sentence, re.I)
    if not m:
        return None
    subj = m.group(1).lower().replace("the ", "").strip()
    if subj in user or subj.split()[-1] in user:
        return True
    if subj in other or subj.split()[-1] in other:
        return False
    return None


def detect_vague_discretion(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    seen_clauses = set()
    for m in _DISCRETION.finditer(ctx.text):
        clause = ctx.clause_at(m.start())
        if clause and clause.id in seen_clauses:
            continue
        s, _ = sentence_bounds(ctx.text, m.start(), m.end())
        holder_user = _holder_is_user(ctx, ctx.text[s:m.start()])
        favorable = holder_user is True
        if clause:
            seen_clauses.add(clause.id)
        out.append(_finding(
            ctx, title="Decision left to the other party's sole discretion", severity="medium",
            start=m.start(), end=m.end(),
            explanation=(f"The phrase \"{m.group(0)}\" lets one side decide without objective criteria or any duty to act reasonably. "
                         "Outcomes that look guaranteed elsewhere may in practice be optional."),
            recommendation="Replace with objective criteria or \"acting reasonably and in good faith\", with written reasons.",
            hidden_reason="Vague discretion language quietly overrides otherwise specific commitments.",
            favorable=favorable, confidence=0.65,
        ))
        if len(out) >= 4:
            break
    return out


def detect_external_references(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    headings = " ".join(clause_label(c) for c in ctx.clauses).lower()
    missing_refs: Dict[str, int] = {}
    for m in _SCHEDULE_REF.finditer(ctx.text):
        ref = f"{m.group(1)} {m.group(2)}"
        if ref.lower() not in headings and ref not in missing_refs:
            missing_refs[ref] = m.start()
    missing_ref_clauses = {c.id for c in (ctx.clause_at(p) for p in missing_refs.values()) if c}

    seen = set(missing_ref_clauses)
    for m in _EXTERNAL_REF.finditer(ctx.text):
        clause = ctx.clause_at(m.start())
        key = clause.id if clause else m.group(0)
        if key in seen:
            continue
        seen.add(key)
        token = m.group(0).lower()
        if token.startswith(("http", "www")):
            title = "Binding terms live at a web link"
        elif "from time to time" in token:
            title = "Terms can change via documents \"amended from time to time\""
        else:
            title = "Terms incorporated by reference from another document"
        out.append(_finding(
            ctx, title=title,
            severity="medium", start=m.start(), end=m.end(),
            explanation=("Part of what you are agreeing to is defined outside this document. "
                         "It can be changed later without a fresh signature, and you may never have read it."),
            recommendation="Ask for referenced documents to be attached and frozen at the signing version, with notice and consent for material changes.",
            hidden_reason="Obligations are incorporated by reference, so they do not appear in the text you are reading.",
        ))
        if len(out) >= 3:
            break

    for ref, pos in list(missing_refs.items())[:2]:
        out.append(_finding(
            ctx, title=f"{ref} is referenced but not included", severity="medium", start=pos, end=pos + len(ref),
            explanation=f"The document relies on {ref}, which is not part of the text provided. Terms inside it are binding but cannot be reviewed.",
            recommendation=f"Request {ref} before signing and confirm it is attached to the final version.",
            hidden_reason="Key terms are delegated to an attachment that is missing from the document.",
        ))
    return out


def detect_deemed_acceptance(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    seen = set()
    for m in _DEEMED.finditer(ctx.text):
        clause = ctx.clause_at(m.start())
        if clause and clause.id in seen:
            continue
        if clause:
            seen.add(clause.id)
        renew = "renew" in m.group(0).lower()
        out.append(_finding(
            ctx,
            title="Contract renews automatically" if renew else "Consent is assumed from silence or continued use",
            severity="medium", start=m.start(), end=m.end(),
            explanation=("Doing nothing locks you in. The agreement continues or new terms bind you unless you actively object within a window that is easy to miss."),
            recommendation="Ask for advance written reminders, a reasonable opt-out window, and express consent for material changes.",
            hidden_reason="Consent or renewal happens automatically, without any action from you.",
        ))
        if len(out) >= 3:
            break
    return out


def detect_survival_and_penalties(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    m = _SURVIVAL.search(ctx.text)
    if m:
        out.append(_finding(
            ctx, title="Obligations survive termination indefinitely", severity="medium", start=m.start(), end=m.end(),
            explanation="Some duties never expire, even long after the relationship ends.",
            recommendation="Limit survival to a fixed period (2-3 years), except for genuine trade secrets.",
            hidden_reason="Survival terms sit in boilerplate and extend obligations without a visible end date.",
        ))
    seen = set()
    for m in _PENALTY.finditer(ctx.text):
        clause = ctx.clause_at(m.start())
        if clause and clause.id in seen:
            continue
        s, e = sentence_bounds(ctx.text, m.start(), m.end())
        if re.search(r"\b(not|no|never|without)\b[^.;]{0,50}$", ctx.text[s:m.start()], re.I):
            continue
        if clause:
            seen.add(clause.id)
        payer_is_user = _payer_is_user(ctx, ctx.text[s:e])
        out.append(_finding(
            ctx, title="Financial penalty or repayment on exit", severity="high", start=m.start(), end=m.end(),
            explanation="Leaving, cancelling or breaching triggers a payment obligation that may exceed any real loss.",
            recommendation="Make any repayment pro-rata, tied to documented actual costs, and waived if the other side terminates without cause.",
            hidden_reason="Penalty terms are framed as damages or reimbursement, so they are easy to read past.",
            favorable=payer_is_user is False, category="financial", confidence=0.65,
        ))
        if len(seen) >= 2:
            break
    return out


def detect_obligation_asymmetry(ctx: AnalysisContext) -> List[Finding]:
    user, other = _aliases(ctx)
    counts = {"user": 0, "other": 0}
    first_user_match = None
    for m in _OBLIGATION.finditer(ctx.text):
        subj = m.group("subj").lower().replace("the ", "").strip()
        if subj in user or any(subj == u for u in user):
            counts["user"] += 1
            if first_user_match is None:
                first_user_match = m
        elif subj in other or any(subj == o for o in other):
            counts["other"] += 1
    u, o = counts["user"], counts["other"]
    if u >= 5 and u >= 2.5 * max(1, o) and first_user_match:
        return [_finding(
            ctx, title="Obligations are heavily one-sided", severity="medium",
            start=first_user_match.start(), end=first_user_match.end(), kind="hidden",
            explanation=(f"The document imposes about {u} obligations on you (\"shall\", \"must\", \"agrees to\") "
                         f"but only {o} on the other side. Duties are concentrated on you, while the other party keeps flexibility."),
            recommendation="Ask for reciprocal commitments, for example mutual confidentiality, mutual notice and mutual indemnities.",
            hidden_reason="No single clause looks extreme. The imbalance only shows across the whole document.",
            confidence=0.6,
        )]
    if o >= 5 and o >= 2.5 * max(1, u):
        anchor = next(m for m in _OBLIGATION.finditer(ctx.text) if m.group("subj").lower().replace("the ", "").strip() in other)
        return [_finding(
            ctx, title="Obligations mostly fall on the other party", severity="info", start=anchor.start(), end=anchor.end(),
            explanation=f"The other side carries about {o} obligations versus {u} on you.",
            recommendation="", hidden_reason=None, favorable=True, confidence=0.6,
        )]
    return []


def detect_contradictions(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    for key, label, context_re, unit in _CONTRADICTION_SPECS:
        per_clause: Dict[str, Tuple[float, int, int, str]] = {}
        for clause in ctx.clauses:
            for v in find_durations(clause.text, clause.start):
                s, e = sentence_bounds(ctx.text, v.start, v.end)
                if not context_re.search(ctx.text[s:e]):
                    continue
                if key == "non_compete" and re.search(r"solicit", ctx.text[s:e], re.I) and not re.search(r"compet", ctx.text[max(s, v.start - 120):v.end], re.I):
                    continue
                normalized = round(convert_duration(v.value, v.unit, unit), 1)
                per_clause.setdefault(clause.id, (normalized, v.start, v.end, v.raw))
                break
        values = defaultdict(list)
        for cid, (val, start, end, raw) in per_clause.items():
            values[val].append((cid, start, end, raw))
        if len(values) >= 2:
            items = sorted(((val, entries[0]) for val, entries in values.items()), key=lambda x: x[1][1])
            (v1, (c1, s1, e1, r1)), (v2, (c2, s2, e2, r2)) = items[0], items[1]
            by_id = ctx.clause_by_id
            out.append(_finding(
                ctx, title=f"Conflicting {label.lower()}: {r1} vs {r2}", severity="medium", start=s2, end=e2,
                explanation=(f"{clause_label(by_id[c1])} says {r1} but {clause_label(by_id[c2])} says {r2}. "
                             "Inconsistent terms create disputes, and the drafter usually argues for whichever reading suits them."),
                recommendation=f"Ask for a single, consistent {label.lower()} stated in one place.",
                hidden_reason="The two values appear in different sections, so the conflict is only visible when they are compared.",
                confidence=0.7,
            ))
    return out


def detect_missing_clauses(ctx: AnalysisContext) -> List[Finding]:
    out: List[Finding] = []
    present = {t for c in ctx.clauses for t in c.clause_types}
    text_lower = ctx.text.lower()
    for spec in ctx.playbook.clauses:
        if not spec.expected or spec.missing is None or spec.id in present:
            continue
        if sum(1 for k in spec.keywords if k in text_lower) >= 2:
            continue
        if ctx.perspective.id not in spec.missing.risk_for:
            continue
        out.append(Finding(
            id=ctx.new_id(), kind="missing", severity=spec.missing.severity,
            title=f"Missing: {spec.label}", clause_type=spec.id, clause_label=spec.label, category=spec.category,
            explanation=spec.missing.explanation,
            recommendation=f"Ask for a {spec.label.lower()} clause.",
            market_comparison=spec.market_standard or None,
            references=source_links(spec.sources, spec.references, jurisdiction=ctx.jurisdiction), confidence=0.7, sources=["playbook"], verified=True,
            redline=None,
        ))
    return out


def _heading_related(heading: str, clause_type: Optional[str], ctx: AnalysisContext) -> bool:
    if not clause_type:
        return True
    spec = ctx.playbook.clause(clause_type)
    if spec is None:
        return True
    h = heading.lower()
    if any(k in h for k in spec.keywords) or any(w in h for w in re.findall(r"[a-z]{4,}", spec.label.lower())):
        return True
    sim = embedder.similarity([heading], [f"{spec.label}. {spec.description}"])[0][0]
    threshold = 0.62 if embedder.backend.startswith("neural") else 0.12
    return float(sim) >= threshold


def mark_buried(ctx: AnalysisContext, findings: List[Finding]) -> None:
    by_id = ctx.clause_by_id
    for f in findings:
        if f.favorable or f.kind not in ("risk", "hidden") or SEVERITY_ORDER[f.severity] < SEVERITY_ORDER["medium"]:
            continue
        clause: Optional[Clause] = by_id.get(f.clause_ids[0]) if f.clause_ids else None
        if not clause or not clause.heading:
            continue
        catch_all = bool(_CATCH_ALL_HEADINGS.search(clause.heading))
        if catch_all or not _heading_related(clause.heading, f.clause_type, ctx):
            f.kind = "hidden"
            f.buried = True
            reason = f"Appears under the heading \"{clause.heading}\""
            if f.clause_label:
                reason += f" instead of a {f.clause_label} section"
            reason += ", where readers are unlikely to look for it."
            f.hidden_reason = f.hidden_reason or reason


def run_hidden_detectors(ctx: AnalysisContext) -> List[Finding]:
    findings: List[Finding] = []
    for detector in (detect_vague_discretion, detect_external_references, detect_deemed_acceptance,
                     detect_survival_and_penalties, detect_obligation_asymmetry, detect_contradictions):
        findings.extend(detector(ctx))
    return findings
