"""Score a pipeline run against a hand-labeled gold file (tests/fixtures/gold/*.yaml)."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.analysis.verifier import locate_quote
from app.models.schemas import AnalysisResult, Detection, Finding

GOLD_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "gold"
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


@dataclass
class Label:
    id: str
    title: str
    kind: Optional[str] = None
    min_severity: Optional[str] = None

    def matches(self, f: Finding) -> bool:
        if self.kind and f.kind != self.kind:
            return False
        return re.search(self.title, f.title, re.I) is not None

    def severity_ok(self, f: Finding) -> bool:
        return self.min_severity is None or SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER[self.min_severity]


@dataclass
class Gold:
    sample: str
    doc_type: str
    perspective: str
    jurisdiction: Optional[str] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    required: List[Label] = field(default_factory=list)
    acceptable: List[Label] = field(default_factory=list)
    forbidden: List[Label] = field(default_factory=list)
    benchmarks: List[dict] = field(default_factory=list)


@dataclass
class SampleScore:
    sample: str
    detection_ok: bool
    detection_note: str
    true_positives: int
    false_positives: List[str]
    missed: List[str]
    severity_misses: List[str]
    forbidden_hits: List[str]
    benchmark_misses: List[str]
    score: int
    score_ok: bool
    quotes_total: int
    quotes_unverifiable: int
    required_total: int = 0
    timings_ms: Dict[str, float] = field(default_factory=dict)

    @property
    def flagged(self) -> int:
        return self.true_positives + len(self.false_positives)

    @property
    def recall_hits(self) -> int:
        return self.required_total - len(self.missed)


def load_gold(path: Path) -> Gold:
    raw = yaml.safe_load(path.read_text())
    labels = {k: [Label(**item) for item in raw.pop(k, []) or []] for k in ("required", "acceptable", "forbidden")}
    return Gold(**raw, **labels)


def all_gold() -> List[Gold]:
    return [load_gold(p) for p in sorted(GOLD_DIR.glob("*.yaml"))]


def _is_risk(f: Finding) -> bool:
    return not f.favorable and f.severity != "info"


def score_run(gold: Gold, detection: Detection, result: AnalysisResult, timings_ms: Optional[Dict[str, float]] = None,
              text: Optional[str] = None) -> SampleScore:
    notes = []
    if detection.doc_type != gold.doc_type:
        notes.append(f"doc_type {detection.doc_type} != {gold.doc_type}")
    if gold.jurisdiction and detection.jurisdiction != gold.jurisdiction:
        notes.append(f"jurisdiction {detection.jurisdiction} != {gold.jurisdiction}")
    if result.perspective != gold.perspective:
        notes.append(f"perspective {result.perspective} != {gold.perspective}")

    risks = [f for f in result.findings if _is_risk(f)]
    missed, severity_misses = [], []
    for label in gold.required:
        hits = [f for f in risks if label.matches(f)]
        if not hits:
            missed.append(label.id)
        elif not any(label.severity_ok(f) for f in hits):
            severity_misses.append(f"{label.id} ({hits[0].severity} < {label.min_severity})")

    labels = gold.required + gold.acceptable
    tp, fps = 0, []
    for f in risks:
        if any(label.matches(f) for label in labels):
            tp += 1
        else:
            fps.append(f"{f.severity}: {f.title}")

    forbidden_hits = [f"{label.id}: {f.title}" for label in gold.forbidden for f in result.findings if label.matches(f)]

    bench = {b.metric_id: b for b in result.benchmarks}
    benchmark_misses = []
    for spec in gold.benchmarks:
        b = bench.get(spec["metric"])
        if b is None:
            benchmark_misses.append(f"{spec['metric']}: not extracted")
        elif abs(b.value - spec["value"]) > 1e-6 or b.position != spec["position"]:
            benchmark_misses.append(f"{spec['metric']}: got {b.value:g} {b.position}, want {spec['value']:g} {spec['position']}")

    score = result.scorecard.overall
    score_ok = (gold.score_min is None or score >= gold.score_min) and (gold.score_max is None or score <= gold.score_max)

    quoted = [f for f in result.findings if f.quote]
    unverifiable = 0
    if text is not None:
        unverifiable = sum(1 for f in quoted if locate_quote(f.quote, text) is None)

    return SampleScore(
        sample=gold.sample, detection_ok=not notes, detection_note="; ".join(notes), true_positives=tp,
        false_positives=fps, missed=missed, severity_misses=severity_misses, forbidden_hits=forbidden_hits,
        benchmark_misses=benchmark_misses, score=score, score_ok=score_ok, quotes_total=len(quoted),
        quotes_unverifiable=unverifiable, timings_ms=timings_ms or {}, required_total=len(gold.required),
    )
