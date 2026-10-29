"""NLP Lab: exposes the four classic pipeline layers for a stored analysis (academic / explainability view)."""
import time
from collections import Counter
from typing import List

from app.analysis.values import find_durations, find_money, find_percents
from app.lab.cleaner import clean_and_filter_tokens
from app.lab.lemmatizer import lemmatizer_name, tag_pos_and_lemmatize
from app.lab.ngrams import get_all_ngrams
from app.lab.readability import compute_readability_metrics
from app.lab.schemas import (
    ClauseClassification, ExtractedValue, LabLayer1, LabLayer2, LabLayer3, LabLayer4, LabResult,
)
from app.lab.sentiment import analyze_document_sentiment
from app.lab.textrank import extract_textrank_summary
from app.lab.tfidf import compute_tfidf_keywords
from app.lab.tokenizer import segment_sentences, sentence_tokenizer_name, tokenize_words
from app.models.schemas import AnalysisResult, Detection
from app.structure.segmenter import clause_label

_OBLIGATION_MARKERS = ("shall ", "must ", "agrees to", "is required to", "will be required", "undertakes to")


def _layer1(text: str):
    t = time.perf_counter()
    sentences = segment_sentences(text)
    tokens = tokenize_words(text)
    cleaned, removed, reduction, vocab = clean_and_filter_tokens(tokens)
    pos, lemmas = tag_pos_and_lemmatize(tokens[:4000])
    layer = LabLayer1(
        execution_time_ms=0, total_characters=len(text), raw_word_count=len(tokens), sentence_count=len(sentences),
        sample_sentences=sentences[:5], stop_words_removed_count=removed, token_reduction_percent=reduction,
        vocabulary_size=vocab, pos_distribution=pos, sample_lemmas=lemmas, sentence_tokenizer=sentence_tokenizer_name(),
        lemmatizer=lemmatizer_name(),
    )
    layer.execution_time_ms = round((time.perf_counter() - t) * 1000, 1)
    return layer, sentences, tokens, cleaned


def _layer2(sentences: List[str], tokens: List[str], cleaned: List[str]) -> LabLayer2:
    t = time.perf_counter()
    unigrams, bigrams, trigrams = get_all_ngrams(cleaned, tokens)
    layer = LabLayer2(
        execution_time_ms=0, tfidf_top_keywords=compute_tfidf_keywords(sentences), unigrams=unigrams,
        bigrams=bigrams, trigrams=trigrams, sentiment=analyze_document_sentiment(sentences),
        readability=compute_readability_metrics(sentences, tokens),
    )
    layer.execution_time_ms = round((time.perf_counter() - t) * 1000, 1)
    return layer


def _fmt_money(v) -> str:
    return f"{v.unit} {v.value:,.0f}"


def _layer3(text: str, result: AnalysisResult, detection: Detection) -> LabLayer3:
    t = time.perf_counter()
    durations, money, percents = find_durations(text), find_money(text), find_percents(text)
    values: List[ExtractedValue] = []
    for d in durations[:12]:
        values.append(ExtractedValue(kind="duration", text=d.raw, normalized=f"{d.value:g} {d.unit}{'s' if d.value != 1 else ''}"))
    for m in money[:8]:
        values.append(ExtractedValue(kind="money", text=m.raw, normalized=_fmt_money(m)))
    for p in percents[:8]:
        values.append(ExtractedValue(kind="percent", text=p.raw, normalized=f"{p.value:g}%"))

    classifications = []
    for c in result.clauses:
        top = sorted(c.type_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
        classifications.append(ClauseClassification(
            clause_id=c.id, label=clause_label(c), top_types=[{k: round(v, 3)} for k, v in top], assigned=c.clause_types,
        ))

    sources = Counter(s for f in result.findings for s in f.sources)
    kinds = Counter(f.kind for f in result.findings)
    layer = LabLayer3(
        execution_time_ms=0,
        clause_count=len(result.clauses),
        typed_clause_count=sum(1 for c in result.clauses if c.clause_types),
        embedding_backend=result.engine.embedding_backend,
        doc_type_candidates=[{c.label: c.score} for c in detection.candidates[:5]],
        jurisdiction_evidence=detection.jurisdiction_evidence[:6],
        parties=[{"name": p.name, "role": p.role or ""} for p in result.parties],
        values=values,
        value_counts={"duration": len(durations), "money": len(money), "percent": len(percents)},
        classifications=classifications,
        findings_by_source=dict(sources),
        findings_by_kind=dict(kinds),
    )
    layer.execution_time_ms = round((time.perf_counter() - t) * 1000, 1)
    return layer


def _layer4(sentences: List[str], result: AnalysisResult) -> LabLayer4:
    t = time.perf_counter()
    textrank = extract_textrank_summary(sentences, top_k=5)
    obligations = [s for s in sentences if any(m in s.lower() for m in _OBLIGATION_MARKERS) and len(s) < 260][:6]
    e = result.engine
    layer = LabLayer4(
        execution_time_ms=0, textrank_summary=textrank, summary=result.summary, summary_source=result.summary_source,
        obligations=obligations, engine_mode=e.mode, llm_provider=f"{e.llm_provider}:{e.llm_model}" if e.llm_provider else "none",
        llm_batches=e.llm_batches, llm_findings_proposed=e.llm_findings_proposed,
        llm_findings_rejected_unverified=e.llm_findings_rejected_unverified,
        verified_findings=sum(1 for f in result.findings if f.verified), stage_timings_ms=e.stage_timings_ms,
    )
    layer.execution_time_ms = round((time.perf_counter() - t) * 1000, 1)
    return layer


def run_lab(text: str, result: AnalysisResult, detection: Detection) -> LabResult:
    layer1, sentences, tokens, cleaned = _layer1(text)
    return LabResult(
        analysis_id=result.analysis_id,
        layer1=layer1,
        layer2=_layer2(sentences, tokens, cleaned),
        layer3=_layer3(text, result, detection),
        layer4=_layer4(sentences, result),
    )
