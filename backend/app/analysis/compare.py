"""Clause-aligned comparison of two analyses (e.g. two offer letters, or two vendors' MSAs)."""
from typing import Dict, List, Optional

from app.analysis.context import SEVERITY_ORDER
from app.models.schemas import (
    AnalysisResult, BenchmarkCompare, Clause, CompareCell, CompareResult, CompareRow, CompareSide, Finding,
)
from app.nlp.embeddings import embedder
from app.playbooks.loader import get_playbook
from app.structure.segmenter import clause_label

_ALIGN_THRESHOLD = 0.55


def _side(r: AnalysisResult) -> CompareSide:
    return CompareSide(
        analysis_id=r.analysis_id, filename=r.filename, doc_type_label=r.doc_type_label,
        perspective_label=r.perspective_label, jurisdiction_label=r.jurisdiction_label,
        overall=r.scorecard.overall, grade=r.scorecard.grade, risk_level=r.scorecard.risk_level,
        categories=r.scorecard.categories,
    )


def _excerpt(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def _finding_type(f: Finding, by_id: Dict[str, Clause]) -> Optional[str]:
    if f.clause_type:
        return f.clause_type
    for cid in f.clause_ids:
        c = by_id.get(cid)
        if c and c.clause_types:
            return c.clause_types[0]
    return None


def _cells_by_type(r: AnalysisResult) -> Dict[str, CompareCell]:
    by_id = {c.id: c for c in r.clauses}
    cells: Dict[str, CompareCell] = {}
    for c in r.clauses:
        for t in c.clause_types[:1]:
            cell = cells.setdefault(t, CompareCell())
            cell.clause_ids.append(c.id)
            if cell.excerpt is None:
                cell.heading = clause_label(c)
                cell.excerpt = _excerpt(c.text)
    for f in r.findings:
        if f.favorable:
            continue
        t = _finding_type(f, by_id) or "_other"
        cell = cells.setdefault(t, CompareCell())
        if f.kind == "missing":
            cell.missing = True
        cell.findings.append(f.title)
        cell.penalty = round(cell.penalty + f.score_impact, 2)
        if cell.worst is None or SEVERITY_ORDER[f.severity] > SEVERITY_ORDER[cell.worst]:
            cell.worst = f.severity
    return cells


def _verdict(a: Optional[CompareCell], b: Optional[CompareCell]) -> str:
    a_present = a is not None and not (a.missing and not a.clause_ids)
    b_present = b is not None and not (b.missing and not b.clause_ids)
    if a_present and not b_present and not (b and b.missing):
        return "only_a"
    if b_present and not a_present and not (a and a.missing):
        return "only_b"
    pa, pb = (a.penalty if a else 0.0), (b.penalty if b else 0.0)
    if abs(pa - pb) < 1.0:
        return "same"
    return "a_better" if pa < pb else "b_better"


def _align_untyped(ra: AnalysisResult, rb: AnalysisResult) -> List[CompareRow]:
    ua = [c for c in ra.clauses if not c.clause_types and c.heading and len(c.text) > 60]
    ub = [c for c in rb.clauses if not c.clause_types and c.heading and len(c.text) > 60]
    if not ua or not ub:
        return []
    sims = embedder.similarity([f"{c.heading}. {c.text[:800]}" for c in ua], [f"{c.heading}. {c.text[:800]}" for c in ub])
    rows, used = [], set()
    for i, c in enumerate(ua):
        j = int(sims[i].argmax())
        if sims[i][j] < _ALIGN_THRESHOLD or j in used:
            continue
        used.add(j)
        d = ub[j]
        rows.append(CompareRow(
            key=f"align:{c.id}:{d.id}", label=c.heading or clause_label(c),
            a=CompareCell(clause_ids=[c.id], heading=clause_label(c), excerpt=_excerpt(c.text)),
            b=CompareCell(clause_ids=[d.id], heading=clause_label(d), excerpt=_excerpt(d.text)),
            verdict="same", similarity=round(float(sims[i][j]), 3),
        ))
    return rows[:8]


def _benchmarks(ra: AnalysisResult, rb: AnalysisResult) -> List[BenchmarkCompare]:
    a_map = {b.metric_id: b for b in ra.benchmarks}
    b_map = {b.metric_id: b for b in rb.benchmarks}
    rank = {"favorable": 0, "neutral": 1, "unfavorable": 2}
    out = []
    for mid in dict.fromkeys(list(a_map) + list(b_map)):
        x, y = a_map.get(mid), b_map.get(mid)
        better = None
        if x and y:
            better = "same" if rank[x.assessment] == rank[y.assessment] else ("a" if rank[x.assessment] < rank[y.assessment] else "b")
        out.append(BenchmarkCompare(
            metric_id=mid, label=(x or y).label, a_display=x.display_value if x else None, b_display=y.display_value if y else None,
            a_assessment=x.assessment if x else None, b_assessment=y.assessment if y else None, better=better,
        ))
    return out


def compare_analyses(ra: AnalysisResult, rb: AnalysisResult) -> CompareResult:
    warnings = []
    if ra.doc_type != rb.doc_type:
        warnings.append(f"Different document types ({ra.doc_type_label} vs {rb.doc_type_label}); clause alignment is approximate.")
    if ra.perspective != rb.perspective:
        warnings.append("The two analyses were run from different perspectives, so their scores are not directly comparable.")

    pa, pb = get_playbook(ra.doc_type), get_playbook(rb.doc_type)
    ca, cb = _cells_by_type(ra), _cells_by_type(rb)
    order = [s.id for s in pa.clauses] + [s.id for s in pb.clauses if s.id not in {x.id for x in pa.clauses}]
    keys = [k for k in order if k in ca or k in cb] + [k for k in dict.fromkeys(list(ca) + list(cb)) if k not in order]

    rows: List[CompareRow] = []
    for k in keys:
        spec = pa.clause(k) or pb.clause(k)
        label = spec.label if spec else ("Other findings" if k == "_other" else k.replace("_", " ").title())
        a, b = ca.get(k), cb.get(k)
        rows.append(CompareRow(key=k, label=label, a=a, b=b, verdict=_verdict(a, b)))
    rows.extend(_align_untyped(ra, rb))

    diff = ra.scorecard.overall - rb.scorecard.overall
    better = "tie" if abs(diff) < 3 else ("a" if diff > 0 else "b")
    a_wins = sum(1 for r in rows if r.verdict == "a_better")
    b_wins = sum(1 for r in rows if r.verdict == "b_better")
    if better == "tie":
        headline = f"Both documents carry similar overall risk ({ra.scorecard.overall} vs {rb.scorecard.overall})."
    else:
        win, lose = (ra, rb) if better == "a" else (rb, ra)
        headline = (f"{win.filename} is the safer document for the {win.perspective_label.lower()} "
                    f"({win.scorecard.overall} vs {lose.scorecard.overall}).")
    headline += f" A is better on {a_wins} clause areas, B on {b_wins}."

    return CompareResult(a=_side(ra), b=_side(rb), rows=rows, benchmarks=_benchmarks(ra, rb), better=better,
                         headline=headline, warnings=warnings)
