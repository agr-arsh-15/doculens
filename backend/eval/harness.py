"""Run the DocuLens pipeline in-process on raw bytes, without the API or the database."""
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from app.analysis.engine import run_analysis
from app.classify.detector import detect
from app.classify.parties import extract_parties
from app.ingestion.parser import parse_document
from app.models.schemas import AnalysisResult, Detection
from app.playbooks.loader import get_playbook
from app.structure.segmenter import segment_document


@dataclass
class PipelineRun:
    detection: Detection
    result: AnalysisResult
    text: str
    timings_ms: Dict[str, float] = field(default_factory=dict)


def analyze_bytes(
    data: bytes,
    filename: str,
    *,
    doc_type: Optional[str] = None,
    perspective: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    use_llm: bool = False,
    privacy_mode: bool = False,
) -> PipelineRun:
    timings: Dict[str, float] = {}
    t = time.perf_counter()
    parsed = parse_document(data, filename)
    timings["parse"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    clauses = segment_document(parsed.text, parsed.pages, parsed.heading_hints)
    timings["segment"] = (time.perf_counter() - t) * 1000

    t = time.perf_counter()
    detection = detect(parsed.text, use_llm=use_llm)
    timings["detect"] = (time.perf_counter() - t) * 1000

    chosen_type = doc_type or detection.doc_type
    parties = detection.parties if chosen_type == detection.doc_type else extract_parties(parsed.text, get_playbook(chosen_type))
    t = time.perf_counter()
    result = run_analysis(
        analysis_id=uuid.uuid4().hex[:16], document_id="offline", filename=filename, text=parsed.text,
        clauses=clauses, parties=parties, doc_type=chosen_type, perspective=perspective,
        jurisdiction=jurisdiction or detection.jurisdiction, use_llm=use_llm, privacy_mode=privacy_mode,
    )
    timings["analyze"] = (time.perf_counter() - t) * 1000
    timings["total"] = sum(timings.values())
    return PipelineRun(detection=detection, result=result, text=parsed.text, timings_ms=timings)


FIXTURE_DOCS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "documents"


def analyze_sample(name: str, **kwargs) -> PipelineRun:
    path = FIXTURE_DOCS / name
    return analyze_bytes(path.read_bytes(), path.name, **kwargs)
