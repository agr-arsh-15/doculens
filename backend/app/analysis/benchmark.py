from typing import List, Optional, Tuple

from app.analysis.context import AnalysisContext
from app.analysis.values import (ExtractedValue, convert_duration, find_durations, find_percents,
                                 value_near_context)
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.models.schemas import BenchmarkItem, Finding
from app.playbooks.citations import source_links
from app.playbooks.loader import ClauseSpec, MetricSpec


def _fmt(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:g}%"
    rounded = round(value, 1)
    shown = int(rounded) if rounded == int(rounded) else rounded
    label = unit if shown != 1 else unit.rstrip("s")
    return f"{shown} {label}"


def _market_text(rng, unit: str) -> str:
    if rng.min is None and rng.max is None:
        return "n/a"
    if rng.min is not None and rng.max is not None:
        if rng.min == rng.max:
            return "none expected" if rng.max == 0 else _fmt(rng.max, unit)
        if rng.min == 0:
            return f"up to {_fmt(rng.max, unit)}"
        return f"{_fmt(rng.min, unit)} to {_fmt(rng.max, unit)}"
    if rng.max is not None:
        return f"up to {_fmt(rng.max, unit)}"
    return f"at least {_fmt(rng.min, unit)}"


def _extract(metric: MetricSpec, text: str, offset: int) -> Optional[Tuple[float, ExtractedValue]]:
    if metric.extractor == "duration":
        values = [v for v in find_durations(text, offset)]
        hit = value_near_context(text, values, metric.context, offset, metric.exclude_context, metric.prefer_context)
        if hit:
            return convert_duration(hit.value, hit.unit, metric.unit), hit
    elif metric.extractor == "percent":
        hit = value_near_context(text, find_percents(text, offset), metric.context, offset, metric.exclude_context)
        if hit:
            return hit.value, hit
    return None


def _locate(ctx: AnalysisContext, spec: ClauseSpec, metric: MetricSpec):
    for clause in ctx.clauses_of_type(spec.id):
        got = _extract(metric, clause.text, clause.start)
        if got:
            return clause, got
    for clause in ctx.clauses:
        if spec.id in clause.clause_types:
            continue
        text_lower = clause.text.lower()
        if metric.context and any(c in text_lower for c in metric.context) and any(k in text_lower for k in spec.keywords):
            got = _extract(metric, clause.text, clause.start)
            if got:
                return clause, got
    return None, None


def run_benchmarks(ctx: AnalysisContext) -> Tuple[List[BenchmarkItem], List[Finding]]:
    items: List[BenchmarkItem] = []
    findings: List[Finding] = []
    jurisdiction_label = JURISDICTION_LABELS.get(ctx.jurisdiction, ctx.jurisdiction)
    for spec in ctx.playbook.clauses:
        for metric in spec.metrics:
            rng = metric.range_for(ctx.jurisdiction)
            if rng is None:
                continue
            clause, got = _locate(ctx, spec, metric)
            if not got:
                continue
            value, raw = got
            links = source_links(rng.sources)
            if rng.min is not None and value < rng.min - 1e-6:
                position = "below_market"
            elif rng.max is not None and value > rng.max + 1e-6:
                position = "above_market"
            else:
                position = "market"
            worse_side = "above_market" if metric.worse_when == "higher" else "below_market"
            user_at_risk = ctx.perspective.id in metric.risk_for
            if position == "market":
                assessment = "neutral"
            elif position == worse_side:
                assessment = "unfavorable" if user_at_risk else "favorable"
            else:
                assessment = "favorable" if user_at_risk else "unfavorable"
            quote, q_start, q_end = ctx.sentence_quote(raw.start, raw.end)
            market_txt = _market_text(rng, metric.unit)
            scope = "" if metric.jurisdictions.get(ctx.jurisdiction) is None else f" in {jurisdiction_label}"
            note = f"{metric.label}: {_fmt(value, metric.unit)} vs market {market_txt}{scope}."
            if rng.note:
                note += f" {rng.note}."
            items.append(BenchmarkItem(
                metric_id=metric.id, label=metric.label, clause_type=spec.id, value=round(value, 2), unit=metric.unit,
                display_value=raw.raw, market_min=rng.min, market_max=rng.max, typical=rng.typical,
                scale_max=max(metric.scale_max, value * 1.1), position=position, assessment=assessment, note=note,
                sources=links, clause_id=clause.id if clause else None, quote=quote,
                quote_start=q_start, quote_end=q_end,
            ))
            if assessment == "unfavorable" and user_at_risk:
                direction = "longer/higher" if metric.worse_when == "higher" else "shorter/lower"
                findings.append(Finding(
                    id=ctx.new_id(), kind="benchmark", severity=metric.severity_outside,
                    title=f"{metric.label} is outside market range ({_fmt(value, metric.unit)})",
                    clause_type=spec.id, clause_label=spec.label, category=spec.category,
                    clause_ids=[clause.id] if clause else [], quote=quote, quote_start=q_start, quote_end=q_end,
                    explanation=f"{note} This is {direction} than typical market terms, which works against you.",
                    recommendation=f"Negotiate toward the market range ({market_txt}).",
                    market_comparison=note, references=links,
                    confidence=0.8, sources=["rule"], verified=True,
                ))
    return items, findings
