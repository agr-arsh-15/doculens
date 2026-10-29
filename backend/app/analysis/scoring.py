import math
from typing import Dict, List

from app.analysis.context import AnalysisContext
from app.models.schemas import CategoryScore, Coverage, Finding, ScoreContribution, Scorecard
from app.playbooks.loader import CATEGORY_LABELS

SEVERITY_WEIGHT = {"critical": 30.0, "high": 18.0, "medium": 9.0, "low": 4.0, "info": 0.0}
KIND_FACTOR = {"risk": 1.0, "hidden": 1.0, "missing": 0.8, "benchmark": 1.0, "info": 0.0}

RANK_DECAY = 0.9
FORMULA = (
    "Impact per finding = severity weight (critical 30, high 18, medium 9, low 4) x confidence x kind factor "
    "(missing clauses 0.8), then x 0.9^rank when findings are ranked from most to least severe, so repeated "
    "minor issues add less than the first serious ones. Findings that favor you count 0. "
    "Overall = 100 x e^(-sum of impacts / 100). Each category = 100 x e^(-category impacts / 60)."
)


def _grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _risk_level(score: int) -> str:
    if score >= 85:
        return "low"
    if score >= 70:
        return "moderate"
    if score >= 55:
        return "elevated"
    if score >= 40:
        return "high"
    return "severe"


def score_findings(ctx: AnalysisContext, findings: List[Finding]) -> Scorecard:
    category_penalty: Dict[str, float] = {k: 0.0 for k in CATEGORY_LABELS}
    category_count: Dict[str, int] = {k: 0 for k in CATEGORY_LABELS}
    contributions: List[ScoreContribution] = []
    total = 0.0
    base = {id(f): 0.0 if f.favorable else SEVERITY_WEIGHT[f.severity] * f.confidence * KIND_FACTOR.get(f.kind, 1.0)
            for f in findings}
    for f in findings:
        f.score_impact = 0.0
    for rank, f in enumerate(sorted((f for f in findings if base[id(f)] > 0), key=lambda f: base[id(f)], reverse=True)):
        impact = base[id(f)] * RANK_DECAY ** rank
        f.score_impact = round(impact, 2)
        total += impact
        cat = f.category if f.category in category_penalty else "legal_exposure"
        category_penalty[cat] += impact
        category_count[cat] += 1
        contributions.append(ScoreContribution(finding_id=f.id, title=f.title, severity=f.severity, category=cat,
                                               points=round(impact, 1)))

    overall = int(round(100 * math.exp(-total / 100.0)))
    categories = [
        CategoryScore(id=k, label=label, score=int(round(100 * math.exp(-category_penalty[k] / 60.0))),
                      finding_count=category_count[k], penalty=round(category_penalty[k], 1))
        for k, label in CATEGORY_LABELS.items()
    ]
    contributions.sort(key=lambda c: c.points, reverse=True)
    negotiable = sorted((f for f in findings if not f.favorable and f.score_impact > 0 and (f.recommendation or f.redline)),
                        key=lambda f: f.score_impact, reverse=True)

    present = {t for c in ctx.clauses for t in c.clause_types}
    expected = [s for s in ctx.playbook.clauses if s.expected]
    missing = [s.label for s in expected if s.id not in present and not any(
        f.kind != "missing" and f.clause_type == s.id for f in findings)]
    return Scorecard(
        overall=overall,
        grade=_grade(overall),
        risk_level=_risk_level(overall),
        formula=FORMULA,
        categories=categories,
        contributions=contributions,
        top_negotiation=[f.id for f in negotiable[:3]],
        coverage=Coverage(expected=len(expected), present=len(expected) - len(missing), missing=missing),
    )
