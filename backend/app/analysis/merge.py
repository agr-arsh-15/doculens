import re
from typing import List, Optional

from app.analysis.context import SEVERITY_ORDER, finding_sort_key, max_severity
from app.models.schemas import Finding
from app.playbooks.citations import merge_links

_SOURCE_RANK = {"llm": 0, "rule": 1, "playbook": 2, "embedding": 3}

GENERIC_TITLE_PREFIXES = (
    "Decision left to", "Binding terms live", "Terms can change via documents", "Terms incorporated by reference",
    "Contract renews automatically", "Consent is assumed", "Financial penalty or repayment", "Obligations survive",
)


def _is_generic(f: Finding) -> bool:
    return f.title.startswith(GENERIC_TITLE_PREFIXES)


def _generic_covered(generic: Finding, specific: Finding) -> bool:
    if specific.favorable != generic.favorable or not (generic.clause_ids and specific.clause_ids):
        return False
    if generic.clause_ids[0] != specific.clause_ids[0]:
        return False
    if _overlap(generic, specific) >= 0.5:
        return True
    return (generic.clause_type is not None and generic.clause_type == specific.clause_type
            and SEVERITY_ORDER[specific.severity] >= SEVERITY_ORDER[generic.severity])


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower())}


def _overlap(a: Finding, b: Finding) -> float:
    if a.quote_start is None or b.quote_start is None:
        return 0.0
    inter = min(a.quote_end, b.quote_end) - max(a.quote_start, b.quote_start)
    if inter <= 0:
        return 0.0
    shorter = min(a.quote_end - a.quote_start, b.quote_end - b.quote_start) or 1
    return inter / shorter


def _same_issue(a: Finding, b: Finding) -> bool:
    if a.favorable != b.favorable:
        return False
    same_clause = bool(a.clause_ids and b.clause_ids and a.clause_ids[0] == b.clause_ids[0])
    if not same_clause:
        return False
    ta, tb = _tokens(a.title), _tokens(b.title)
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    if jaccard >= 0.35:
        return True
    both_rules = set(a.sources) <= {"rule", "playbook"} and set(b.sources) <= {"rule", "playbook"}
    if both_rules:
        return False
    if _overlap(a, b) >= 0.85:
        return True
    return _overlap(a, b) >= 0.6 and (jaccard >= 0.12 or (a.clause_type is not None and a.clause_type == b.clause_type))


def _quote_key(f: Finding) -> str:
    return re.sub(r"\s+", " ", (f.quote or "").lower()).strip()


def _repeated_text(a: Finding, b: Finding) -> bool:
    """The same wording flagged again elsewhere, e.g. a page that carries both a US and an EU version of the terms."""
    return (a.kind == b.kind and a.favorable == b.favorable and a.title.lower() == b.title.lower()
            and len(_quote_key(a)) >= 30 and _quote_key(a) == _quote_key(b))


_ABSENCE = re.compile(r"^(no|missing|absent|lack|without)\b|\b(missing|absent|not (?:defined|specified|stated))\b", re.I)


def _reported_absent(missing: Finding, other: Finding) -> bool:
    """A reviewer finding such as "No severance or notice period" already covers "Missing: Notice Period"."""
    if other.kind == "missing" or not _ABSENCE.search(other.title):
        return False
    label = re.sub(r"^missing:\s*", "", missing.title, flags=re.I)
    words = _tokens(other.title)
    return any(part and part <= words for part in (_tokens(p) for p in re.split(r"&|,|/|\band\b|\bor\b", label)))


def _absorb(primary: Finding, other: Finding) -> None:
    if other.kind != "benchmark":
        primary.severity = max_severity(primary.severity, other.severity)
    ta, tb = _tokens(primary.title), _tokens(other.title)
    similar = len(ta & tb) / max(1, len(ta | tb)) >= 0.3
    if other.kind == "hidden" and primary.kind == "risk" and similar:
        primary.kind = "hidden"
        primary.hidden_reason = primary.hidden_reason or other.hidden_reason
    primary.sources = list(dict.fromkeys(primary.sources + other.sources))
    primary.references = merge_links(primary.references, other.references)
    primary.ai_comparison = primary.ai_comparison or other.ai_comparison
    primary.confidence = min(0.95, max(primary.confidence, other.confidence) + 0.1)
    primary.explanation = primary.explanation or other.explanation
    primary.recommendation = primary.recommendation or other.recommendation
    primary.redline = primary.redline or other.redline
    if other.kind == "benchmark" and other.market_comparison:
        primary.market_comparison = other.market_comparison
    else:
        primary.market_comparison = primary.market_comparison or other.market_comparison


def merge_findings(findings: List[Finding]) -> List[Finding]:
    ordered = sorted(findings, key=lambda f: (f.kind == "benchmark", min(_SOURCE_RANK.get(s, 9) for s in f.sources or ["rule"]),
                                              -SEVERITY_ORDER[f.severity]))
    merged: List[Finding] = []
    for f in ordered:
        target: Optional[Finding] = None
        if f.kind == "missing":
            if any(m.clause_type == f.clause_type and m.kind != "missing" for m in merged):
                continue
        elif f.kind == "benchmark":
            target = next((m for m in merged if m.kind in ("risk", "hidden") and not m.favorable and m.clause_type == f.clause_type
                           and m.clause_ids[:1] == f.clause_ids[:1]), None)
        else:
            repeat = next((m for m in merged if _repeated_text(m, f)), None)
            if repeat is not None:
                repeat.clause_ids = list(dict.fromkeys(repeat.clause_ids + f.clause_ids))
                _absorb(repeat, f)
                continue
            target = next((m for m in merged if m.kind != "missing" and _same_issue(m, f)), None)
            if target is None:
                if _is_generic(f):
                    target = next((m for m in merged if m.kind != "missing" and not _is_generic(m) and _generic_covered(f, m)), None)
                else:
                    covered = next((m for m in merged if _is_generic(m) and _generic_covered(m, f)), None)
                    if covered is not None:
                        merged[merged.index(covered)] = f
                        _absorb(f, covered)
                        continue
        if target is not None:
            _absorb(target, f)
        else:
            merged.append(f)

    present_types = {m.clause_type for m in merged if m.kind != "missing"}
    merged = [m for m in merged if not (m.kind == "missing" and (
        m.clause_type in present_types or any(_reported_absent(m, o) for o in merged)))]
    merged.sort(key=finding_sort_key)
    for i, f in enumerate(merged, start=1):
        f.id = f"F{i}"
    return merged
