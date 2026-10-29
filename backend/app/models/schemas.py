from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
FindingKind = Literal["risk", "hidden", "missing", "benchmark", "info"]
Source = Literal["rule", "embedding", "llm", "playbook"]


class PageSpan(BaseModel):
    page: int
    start: int
    end: int


class Clause(BaseModel):
    id: str
    number: Optional[str] = None
    heading: Optional[str] = None
    text: str
    start: int
    end: int
    page: Optional[int] = None
    parent_id: Optional[str] = None
    level: int = 0
    clause_types: List[str] = Field(default_factory=list)
    type_scores: Dict[str, float] = Field(default_factory=dict)


class Party(BaseModel):
    name: str
    role: Optional[str] = None


class DocTypeCandidate(BaseModel):
    id: str
    label: str
    score: float


class Perspective(BaseModel):
    id: str
    label: str
    description: str = ""


class Detection(BaseModel):
    doc_type: str
    doc_type_label: str
    doc_type_confidence: float
    candidates: List[DocTypeCandidate]
    jurisdiction: str
    jurisdiction_label: str
    jurisdiction_evidence: List[str] = Field(default_factory=list)
    parties: List[Party] = Field(default_factory=list)
    perspectives: List[Perspective] = Field(default_factory=list)
    default_perspective: str
    method: str


class DocumentOut(BaseModel):
    id: str
    filename: str
    source_type: str
    page_count: int
    char_count: int
    word_count: int
    ocr_used: bool = False
    has_original_file: bool = False
    created_at: str
    detection: Detection
    warnings: List[str] = Field(default_factory=list)


class Redline(BaseModel):
    original: str
    suggested: str


class SourceLink(BaseModel):
    """A trusted source behind a market standard, benchmark or legal reference."""
    id: Optional[str] = None
    title: str
    publisher: str = ""
    url: Optional[str] = None
    tier: Optional[Literal["official", "professional", "law_firm", "news"]] = None


def _coerce_links(value):
    """Analyses stored before sources were linked hold plain-text references."""
    if isinstance(value, list):
        return [{"title": v} if isinstance(v, str) else v for v in value]
    return value


class Finding(BaseModel):
    id: str
    kind: FindingKind
    severity: Severity
    title: str
    clause_type: Optional[str] = None
    clause_label: Optional[str] = None
    category: str = "legal_exposure"
    clause_ids: List[str] = Field(default_factory=list)
    quote: Optional[str] = None
    quote_start: Optional[int] = None
    quote_end: Optional[int] = None
    explanation: str = ""
    recommendation: str = ""
    redline: Optional[Redline] = None
    hidden_reason: Optional[str] = None
    market_comparison: Optional[str] = None
    ai_comparison: Optional[str] = None
    references: List[SourceLink] = Field(default_factory=list)

    _links = field_validator("references", mode="before")(_coerce_links)
    confidence: float = 0.7
    sources: List[Source] = Field(default_factory=list)
    verified: bool = False
    favorable: bool = False
    buried: bool = False
    score_impact: float = 0.0


class BenchmarkItem(BaseModel):
    metric_id: str
    label: str
    clause_type: str
    value: float
    unit: str
    display_value: str
    market_min: Optional[float] = None
    market_max: Optional[float] = None
    typical: Optional[float] = None
    scale_max: float
    position: Literal["below_market", "market", "above_market"]
    assessment: Literal["favorable", "neutral", "unfavorable"]
    note: str = ""
    sources: List[SourceLink] = Field(default_factory=list)
    clause_id: Optional[str] = None
    quote: Optional[str] = None
    quote_start: Optional[int] = None
    quote_end: Optional[int] = None


class CategoryScore(BaseModel):
    id: str
    label: str
    score: int
    finding_count: int
    penalty: float


class ScoreContribution(BaseModel):
    finding_id: str
    title: str
    severity: Severity
    category: str
    points: float


class Coverage(BaseModel):
    expected: int
    present: int
    missing: List[str]


class Scorecard(BaseModel):
    overall: int
    grade: str
    risk_level: Literal["low", "moderate", "elevated", "high", "severe"]
    formula: str
    categories: List[CategoryScore]
    contributions: List[ScoreContribution]
    top_negotiation: List[str]
    coverage: Coverage


class EngineStats(BaseModel):
    mode: Literal["hybrid", "local"]
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_backend: str
    llm_batches: int = 0
    llm_failed_batches: int = 0
    llm_findings_proposed: int = 0
    llm_findings_rejected_unverified: int = 0
    rule_findings: int = 0
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    analysis_id: str
    document_id: str
    filename: str
    doc_type: str
    doc_type_label: str
    jurisdiction: str
    jurisdiction_label: str
    perspective: str
    perspective_label: str
    parties: List[Party]
    summary: str
    summary_source: str
    clauses: List[Clause]
    findings: List[Finding]
    benchmarks: List[BenchmarkItem]
    scorecard: Scorecard
    engine: EngineStats
    playbook_version: str
    prompt_version: str
    text_length: int
    disclaimer: str
    created_at: str


class AnalysisSummary(BaseModel):
    id: str
    document_id: str
    filename: str
    status: str
    doc_type: Optional[str] = None
    doc_type_label: Optional[str] = None
    perspective: Optional[str] = None
    jurisdiction: Optional[str] = None
    overall: Optional[int] = None
    grade: Optional[str] = None
    finding_counts: Dict[str, int] = Field(default_factory=dict)
    engine_mode: Optional[str] = None
    created_at: str


class AnalysisStatus(BaseModel):
    id: str
    document_id: str
    status: Literal["queued", "running", "completed", "failed"]
    error: Optional[str] = None
    cached: bool = False


class DocumentDetail(DocumentOut):
    text: str
    pages: List[PageSpan] = Field(default_factory=list)
    clauses: List[Clause] = Field(default_factory=list)


class PlaybookClauseOut(BaseModel):
    id: str
    label: str
    category: str
    importance: str
    description: str
    market_standard: Optional[str] = None
    sources: List[SourceLink] = Field(default_factory=list)
    references: List[SourceLink] = Field(default_factory=list)


class PlaybookOut(BaseModel):
    id: str
    name: str
    version: str
    description: str
    perspectives: List[Perspective]
    clauses: List[PlaybookClauseOut]
    red_flag_count: int


class TextDocumentRequest(BaseModel):
    text: str
    filename: Optional[str] = "pasted-text.txt"


class AnalysisRequest(BaseModel):
    document_id: str
    doc_type: Optional[str] = None
    perspective: Optional[str] = None
    jurisdiction: Optional[str] = None
    use_llm: bool = True
    privacy_mode: bool = False
    force: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = Field(default_factory=list)


class Citation(BaseModel):
    clause_id: str
    label: str
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    mode: str


class CompareRequest(BaseModel):
    analysis_a: str
    analysis_b: str


class CompareSide(BaseModel):
    analysis_id: str
    filename: str
    doc_type_label: str
    perspective_label: str
    jurisdiction_label: str
    overall: int
    grade: str
    risk_level: str
    categories: List[CategoryScore]


class CompareCell(BaseModel):
    clause_ids: List[str] = Field(default_factory=list)
    heading: Optional[str] = None
    excerpt: Optional[str] = None
    findings: List[str] = Field(default_factory=list)
    worst: Optional[Severity] = None
    penalty: float = 0.0
    missing: bool = False


class CompareRow(BaseModel):
    key: str
    label: str
    a: Optional[CompareCell] = None
    b: Optional[CompareCell] = None
    verdict: Literal["a_better", "b_better", "same", "only_a", "only_b"]
    similarity: Optional[float] = None


class BenchmarkCompare(BaseModel):
    metric_id: str
    label: str
    a_display: Optional[str] = None
    b_display: Optional[str] = None
    a_assessment: Optional[str] = None
    b_assessment: Optional[str] = None
    better: Optional[Literal["a", "b", "same"]] = None


class CompareResult(BaseModel):
    a: CompareSide
    b: CompareSide
    rows: List[CompareRow]
    benchmarks: List[BenchmarkCompare]
    better: Literal["a", "b", "tie"]
    headline: str
    warnings: List[str] = Field(default_factory=list)


class NegotiationEmailRequest(BaseModel):
    finding_ids: List[str] = Field(default_factory=list)
    recipient: Optional[str] = None
    tone: Literal["collaborative", "firm"] = "collaborative"


class NegotiationEmailResponse(BaseModel):
    subject: str
    body: str
    mode: str


class HealthOut(BaseModel):
    status: str
    llm: Dict[str, Any]
    embeddings: Dict[str, Any]
    playbooks: List[str]
    version: str
