from typing import List, Optional

from app.analysis.context import AnalysisContext
from app.analysis.values import find_durations, find_money, sentence_bounds
from app.models.schemas import Clause, Finding, Redline
from app.playbooks.citations import source_links
from app.playbooks.loader import ClauseSpec, PatternRule

MAX_HITS_PER_RULE = 2


def _build_finding(ctx: AnalysisContext, rule: PatternRule, spec: Optional[ClauseSpec], clause: Optional[Clause],
                   start: int, end: int, kind: str) -> Finding:
    quote, q_start, q_end = ctx.sentence_quote(start, end)
    host_spec = spec or (ctx.playbook.clause(clause.clause_types[0]) if clause and clause.clause_types else None)
    risky = ctx.is_risky_for_user(rule.risk_for)
    severity = rule.severity_by_jurisdiction.get(ctx.jurisdiction, rule.severity)
    explanation = rule.explanation
    note = rule.jurisdiction_notes.get(ctx.jurisdiction)
    if note:
        explanation = f"{explanation} {note}"
    if not risky:
        counter = ctx.playbook.counterparty(ctx.perspective.id)
        explanation = (f"This term generally favors you as the {ctx.perspective.label}. "
                       f"For the {counter.label if counter else 'other party'}: {rule.explanation}")
    redline = None
    if rule.redline:
        redline = Redline(original=quote, suggested=rule.redline)
    elif spec and spec.suggested_redline and risky:
        redline = Redline(original=quote, suggested=spec.suggested_redline)
    return Finding(
        id=ctx.new_id(),
        kind="hidden" if kind == "hidden" and risky else ("risk" if risky else "info"),
        severity=severity if risky else "info",
        title=rule.title,
        clause_type=host_spec.id if host_spec else None,
        clause_label=host_spec.label if host_spec else None,
        category=host_spec.category if host_spec else "legal_exposure",
        clause_ids=[clause.id] if clause else [],
        quote=quote,
        quote_start=q_start,
        quote_end=q_end,
        explanation=explanation,
        recommendation=rule.recommendation if risky else "",
        redline=redline if risky else None,
        hidden_reason=rule.hidden_reason if risky else None,
        market_comparison=spec.market_standard if spec and spec.market_standard else None,
        references=source_links(rule.sources, spec.sources if spec else [], spec.references if spec else [],
                                jurisdiction=ctx.jurisdiction),
        confidence=0.8,
        sources=["rule"],
        verified=True,
        favorable=not risky,
    )


def _excluded_by_document(ctx: AnalysisContext, rule: PatternRule) -> bool:
    return rule.exclude_scope == "document" and rule.exclude_regex is not None and bool(rule.exclude_regex.search(ctx.text))


def _scan_clause_rule(ctx: AnalysisContext, rule: PatternRule, spec: Optional[ClauseSpec], kind: str) -> List[Finding]:
    findings: List[Finding] = []
    if _excluded_by_document(ctx, rule):
        return findings
    regex = rule.regex
    exclude = rule.exclude_regex if rule.exclude_scope == "clause" else None
    preferred = ctx.clauses_of_type(spec.id) if spec else []
    ordered = preferred + [c for c in ctx.clauses if c not in preferred]
    for clause in ordered:
        if len(findings) >= MAX_HITS_PER_RULE:
            break
        body_offset = _body_offset(clause)
        m = _best_match(regex, clause.text, body_offset, spec)
        if not m:
            continue
        if exclude and exclude.search(clause.text):
            continue
        if spec and clause not in preferred:
            text_lower = clause.text.lower()
            if not any(k in text_lower for k in spec.keywords):
                continue
        findings.append(_build_finding(ctx, rule, spec, clause, clause.start + m.start(), clause.start + m.end(), kind))
    return findings


def _best_match(regex, text: str, body_offset: int, spec: Optional[ClauseSpec]):
    """Among all matches, prefer the sentence with the most concrete evidence (money, durations, topic keywords)."""
    matches = list(regex.finditer(text, body_offset)) or (list(regex.finditer(text)) if body_offset else [])
    if len(matches) <= 1:
        return matches[0] if matches else None
    keywords = spec.keywords if spec else []

    def evidence(m) -> int:
        s, e = sentence_bounds(text, m.start(), m.end())
        sentence = text[s:e].lower()
        score = sum(1 for k in keywords if k.lower() in sentence)
        score += 3 if find_money(sentence) else 0
        score += 1 if find_durations(sentence) else 0
        return score

    return max(matches, key=lambda m: (evidence(m), -m.start()))


def _body_offset(clause: Clause) -> int:
    """Offset of the clause body, skipping a heading line so quotes point at operative text."""
    if not clause.heading:
        return 0
    newline = clause.text.find("\n")
    if 0 < newline <= 140:
        return newline + 1
    idx = clause.text.find(clause.heading)
    if idx != -1:
        end = idx + len(clause.heading)
        while end < len(clause.text) and clause.text[end] in ":.- ":
            end += 1
        return end if end < len(clause.text) else 0
    return 0


def _scan_document_rule(ctx: AnalysisContext, rule: PatternRule, spec: Optional[ClauseSpec], kind: str) -> List[Finding]:
    findings: List[Finding] = []
    if _excluded_by_document(ctx, rule):
        return findings
    for m in rule.regex.finditer(ctx.text):
        clause = ctx.clause_at(m.start())
        if rule.exclude_scope == "clause" and rule.exclude_regex and clause and rule.exclude_regex.search(clause.text):
            continue
        if any(clause and clause.id in f.clause_ids for f in findings):
            continue
        start = m.start()
        if clause:
            body_start = clause.start + _body_offset(clause)
            if start < body_start < m.end():
                start = body_start
        findings.append(_build_finding(ctx, rule, spec, clause, start, m.end(), kind))
        if len(findings) >= MAX_HITS_PER_RULE:
            break
    return findings


def run_rules(ctx: AnalysisContext) -> List[Finding]:
    findings: List[Finding] = []
    for spec in ctx.playbook.clauses:
        for rule in spec.red_flags:
            scan = _scan_document_rule if rule.scope == "document" else _scan_clause_rule
            findings.extend(scan(ctx, rule, spec, "risk"))
    for rule in ctx.playbook.hidden_patterns:
        findings.extend(_scan_document_rule(ctx, rule, None, "hidden"))
    return findings
