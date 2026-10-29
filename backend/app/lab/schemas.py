from typing import Dict, List

from pydantic import BaseModel


class LemmaSample(BaseModel):
    word: str
    lemma: str
    pos: str


class KeywordScore(BaseModel):
    term: str
    score: float


class NGramItem(BaseModel):
    ngram: str
    frequency: int


class SentimentMetrics(BaseModel):
    compound: float
    positive: float
    neutral: float
    negative: float
    tone_label: str
    tone_explanation: str


class ReadabilityMetrics(BaseModel):
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog_index: float
    avg_words_per_sentence: float
    avg_syllables_per_word: float
    estimated_read_time_minutes: float
    complexity_level: str


class LabLayer1(BaseModel):
    execution_time_ms: float
    total_characters: int
    raw_word_count: int
    sentence_count: int
    sample_sentences: List[str]
    stop_words_removed_count: int
    token_reduction_percent: float
    vocabulary_size: int
    pos_distribution: Dict[str, int]
    sample_lemmas: List[LemmaSample]
    sentence_tokenizer: str
    lemmatizer: str = "WordNet"


class LabLayer2(BaseModel):
    execution_time_ms: float
    tfidf_top_keywords: List[KeywordScore]
    unigrams: List[NGramItem]
    bigrams: List[NGramItem]
    trigrams: List[NGramItem]
    sentiment: SentimentMetrics
    readability: ReadabilityMetrics


class ExtractedValue(BaseModel):
    kind: str
    text: str
    normalized: str


class ClauseClassification(BaseModel):
    clause_id: str
    label: str
    top_types: List[Dict[str, float]]
    assigned: List[str]


class LabLayer3(BaseModel):
    execution_time_ms: float
    clause_count: int
    typed_clause_count: int
    embedding_backend: str
    doc_type_candidates: List[Dict[str, float]]
    jurisdiction_evidence: List[str]
    parties: List[Dict[str, str]]
    values: List[ExtractedValue]
    value_counts: Dict[str, int]
    classifications: List[ClauseClassification]
    findings_by_source: Dict[str, int]
    findings_by_kind: Dict[str, int]


class LabLayer4(BaseModel):
    execution_time_ms: float
    textrank_summary: List[str]
    summary: str
    summary_source: str
    obligations: List[str]
    engine_mode: str
    llm_provider: str
    llm_batches: int
    llm_findings_proposed: int
    llm_findings_rejected_unverified: int
    verified_findings: int
    stage_timings_ms: Dict[str, float]


class LabResult(BaseModel):
    analysis_id: str
    layer1: LabLayer1
    layer2: LabLayer2
    layer3: LabLayer3
    layer4: LabLayer4
