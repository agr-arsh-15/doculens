import re
from functools import lru_cache
from typing import Dict, List, Literal, Optional
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field

from app.config import PLAYBOOKS_DIR

Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["financial", "legal_exposure", "privacy_data", "career_mobility", "termination_exit"]

CATEGORY_LABELS: Dict[str, str] = {
    "financial": "Financial",
    "legal_exposure": "Legal Exposure",
    "privacy_data": "Privacy & Data",
    "career_mobility": "Career & Mobility",
    "termination_exit": "Termination & Exit",
}


SourceTier = Literal["official", "professional", "law_firm", "news"]

SOURCES_FILE = "sources.yaml"


class SourceSpec(BaseModel):
    id: str
    title: str
    publisher: str
    url: str
    tier: SourceTier
    jurisdictions: List[str] = Field(default_factory=list)


class SourceRegistry(BaseModel):
    allowed_domains: Dict[SourceTier, List[str]]
    bot_protected: List[str] = Field(default_factory=list)
    sources: List[SourceSpec]

    def by_id(self) -> Dict[str, SourceSpec]:
        return {s.id: s for s in self.sources}


class RangeSpec(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    typical: Optional[float] = None
    note: Optional[str] = None
    sources: List[str] = Field(default_factory=list)


class MetricSpec(BaseModel):
    id: str
    label: str
    unit: Literal["days", "months", "hours", "percent", "multiple", "years"]
    extractor: Literal["duration", "percent", "multiple"]
    context: List[str] = Field(default_factory=list)
    exclude_context: List[str] = Field(default_factory=list)
    prefer_context: List[str] = Field(default_factory=list)
    range: Optional[RangeSpec] = None
    scale_max: float
    worse_when: Literal["higher", "lower"]
    risk_for: List[str]
    severity_outside: Severity = "medium"
    jurisdictions: Dict[str, RangeSpec] = Field(default_factory=dict)

    def range_for(self, jurisdiction: str) -> Optional[RangeSpec]:
        """The sourced range for this jurisdiction; None when no source covers it (no benchmark is shown)."""
        return self.jurisdictions.get(jurisdiction, self.range)

    def all_ranges(self) -> List[RangeSpec]:
        return ([self.range] if self.range else []) + list(self.jurisdictions.values())


class PatternRule(BaseModel):
    id: str
    title: str
    pattern: str
    scope: Literal["clause", "document"] = "clause"
    severity: Severity
    risk_for: List[str]
    explanation: str
    recommendation: str = ""
    redline: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    hidden_reason: Optional[str] = None
    jurisdiction_notes: Dict[str, str] = Field(default_factory=dict)
    severity_by_jurisdiction: Dict[str, Severity] = Field(default_factory=dict)
    exclude_if: Optional[str] = None
    exclude_scope: Literal["clause", "document"] = "clause"

    @property
    def regex(self) -> re.Pattern:
        return _compile(self.pattern)

    @property
    def exclude_regex(self) -> Optional[re.Pattern]:
        return _compile(self.exclude_if) if self.exclude_if else None


class MissingSpec(BaseModel):
    severity: Severity
    risk_for: List[str]
    explanation: str


class ClauseSpec(BaseModel):
    id: str
    label: str
    category: Category
    importance: Literal["critical", "high", "medium", "low"]
    description: str
    keywords: List[str]
    prototype: str
    expected: bool = False
    missing: Optional[MissingSpec] = None
    market_standard: str = ""
    sources: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    suggested_redline: Optional[str] = None
    metrics: List[MetricSpec] = Field(default_factory=list)
    red_flags: List[PatternRule] = Field(default_factory=list)


class PerspectiveSpec(BaseModel):
    id: str
    label: str
    description: str = ""
    aliases: List[str] = Field(default_factory=list)


class DetectionSpec(BaseModel):
    title_keywords: List[str]
    prototypes: List[str]


class Playbook(BaseModel):
    id: str
    name: str
    version: str
    description: str
    detection: DetectionSpec
    perspectives: List[PerspectiveSpec]
    default_perspective: str
    clauses: List[ClauseSpec]
    hidden_patterns: List[PatternRule] = Field(default_factory=list)

    def clause(self, clause_id: str) -> Optional[ClauseSpec]:
        return next((c for c in self.clauses if c.id == clause_id), None)

    def perspective(self, perspective_id: Optional[str]) -> PerspectiveSpec:
        return next((p for p in self.perspectives if p.id == perspective_id), None) or next(
            p for p in self.perspectives if p.id == self.default_perspective
        )

    def counterparty(self, perspective_id: str) -> Optional[PerspectiveSpec]:
        return next((p for p in self.perspectives if p.id != perspective_id), None)


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


def url_host(url: str) -> str:
    return urlparse(url).hostname or ""


def domain_allowed(host: str, domains: List[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


@lru_cache(maxsize=1)
def load_sources() -> SourceRegistry:
    data = yaml.safe_load((PLAYBOOKS_DIR / SOURCES_FILE).read_text(encoding="utf-8"))
    registry = SourceRegistry.model_validate(data)
    seen = set()
    for s in registry.sources:
        if s.id in seen:
            raise RuntimeError(f"Duplicate source id: {s.id}")
        seen.add(s.id)
        if not s.url.startswith("https://"):
            raise RuntimeError(f"Source {s.id} must use https: {s.url}")
        if not domain_allowed(url_host(s.url), registry.allowed_domains.get(s.tier, [])):
            raise RuntimeError(f"Source {s.id} ({url_host(s.url)}) is not on the allowed {s.tier} domain list")
    return registry


def resolve_sources(ids: List[str]) -> List[SourceSpec]:
    by_id = load_sources().by_id()
    return [by_id[i] for i in dict.fromkeys(ids) if i in by_id]


def _check_source_ids(book: "Playbook", known: Dict[str, SourceSpec]) -> None:
    def check(ids: List[str], where: str) -> None:
        for i in ids:
            if i not in known:
                raise RuntimeError(f"Playbook {book.id}: unknown source id '{i}' in {where}")

    for clause in book.clauses:
        check(clause.sources, f"{clause.id}.sources")
        check(clause.references, f"{clause.id}.references")
        for metric in clause.metrics:
            for rng in metric.all_ranges():
                check(rng.sources, f"{clause.id}.{metric.id}")
        for rule in clause.red_flags:
            check(rule.sources, f"{clause.id}.{rule.id}")
    for rule in book.hidden_patterns:
        check(rule.sources, rule.id)


@lru_cache(maxsize=1)
def load_playbooks() -> Dict[str, Playbook]:
    known = load_sources().by_id()
    books: Dict[str, Playbook] = {}
    for path in sorted(PLAYBOOKS_DIR.glob("*.yaml")):
        if path.name == SOURCES_FILE:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        book = Playbook.model_validate(data)
        for clause in book.clauses:
            for rule in clause.red_flags:
                rule.regex  # fail fast on invalid patterns
        for rule in book.hidden_patterns:
            rule.regex
        _check_source_ids(book, known)
        books[book.id] = book
    if "generic_contract" not in books:
        raise RuntimeError("generic_contract playbook is required as the fallback")
    return books


def get_playbook(doc_type: Optional[str]) -> Playbook:
    books = load_playbooks()
    return books.get(doc_type or "", books["generic_contract"])


def playbook_versions() -> str:
    return ",".join(f"{b.id}@{b.version}" for b in load_playbooks().values())
