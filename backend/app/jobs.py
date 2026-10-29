"""In-process analysis jobs with progress events for the SSE stream."""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.analysis.engine import run_analysis
from app.config import ANALYSIS_WORKERS
from app.classify.parties import extract_parties
from app.llm.provider import LLMProvider
from app.models.schemas import Clause, Detection
from app.playbooks.loader import get_playbook
from app.storage import db

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=ANALYSIS_WORKERS, thread_name_prefix="analysis")

# Stages that already ran at upload time; replayed so the tracker shows the whole pipeline.
_UPLOAD_STAGES = [("parsing", "Parsing document", 2), ("segmenting", "Segmenting clauses", 4), ("classifying", "Classifying document", 6)]


@dataclass
class Job:
    id: str
    events: List[dict] = field(default_factory=list)
    done: bool = False
    created: float = field(default_factory=time.time)
    cond: threading.Condition = field(default_factory=threading.Condition)

    def publish(self, event: dict) -> None:
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()


_jobs: Dict[str, Job] = {}
_lock = threading.Lock()


def get_job(analysis_id: str) -> Optional[Job]:
    return _jobs.get(analysis_id)


def _gc() -> None:
    cutoff = time.time() - 3600
    with _lock:
        for k in [k for k, j in _jobs.items() if j.done and j.created < cutoff]:
            _jobs.pop(k, None)


def _finding_counts(result) -> dict:
    counts: Dict[str, int] = {}
    for f in result.findings:
        key = "favorable" if f.favorable else f.severity
        counts[key] = counts.get(key, 0) + 1
        if f.kind == "hidden" and not f.favorable:
            counts["hidden"] = counts.get("hidden", 0) + 1
        if f.kind == "missing":
            counts["missing"] = counts.get("missing", 0) + 1
    return counts


def _run(job: Job, doc: db.DocumentRow, user_id: str, doc_type: str, perspective: str, jurisdiction: str,
         provider: Optional[LLMProvider], privacy_mode: bool, notices: List[str]):
    db.update_analysis(job.id, status="running")
    for stage, label, pct in _UPLOAD_STAGES:
        job.publish({"stage": stage, "label": label, "progress": pct, "status": "running"})

    def progress(stage: str, label: str, pct: int):
        if stage == "done":
            return
        job.publish({"stage": stage, "label": label, "progress": pct, "status": "running"})

    try:
        detection = Detection.model_validate_json(doc.detection_json)
        clauses = [Clause.model_validate(c) for c in json.loads(doc.clauses_json)]
        parties = detection.parties if doc_type == detection.doc_type else extract_parties(doc.text, get_playbook(doc_type))
        result = run_analysis(
            analysis_id=job.id, document_id=doc.id, filename=doc.filename, text=doc.text, clauses=clauses,
            parties=parties,
            doc_type=doc_type, perspective=perspective, jurisdiction=jurisdiction, use_llm=provider is not None,
            privacy_mode=privacy_mode, progress=progress, provider=provider, notices=notices,
        )
        degraded = {"cache_key": ""} if result.engine.llm_failed_batches else {}
        db.update_analysis(
            job.id, **degraded, status="completed", result_json=result.model_dump_json(), overall=result.scorecard.overall,
            grade=result.scorecard.grade, doc_type=result.doc_type, doc_type_label=result.doc_type_label,
            perspective=result.perspective, jurisdiction=result.jurisdiction,
            finding_counts_json=json.dumps(_finding_counts(result)), engine_mode=result.engine.mode,
        )
        db.record_event(user_id, "analysis", doc_type=result.doc_type, jurisdiction=result.jurisdiction,
                        mode=result.engine.mode, score=result.scorecard.overall,
                        own_key=bool(provider and provider.owned_by_user))
        if provider is not None and result.engine.llm_failed_batches:
            db.record_event(user_id, "llm_fallback", failed_batches=result.engine.llm_failed_batches)
        job.publish({"stage": "done", "label": "Analysis complete", "progress": 100, "status": "completed"})
    except Exception:  # surface any engine failure to the client instead of hanging the stream
        log.exception("Analysis %s failed", job.id)
        message = "Analysis failed because of an internal error. Please try again."
        db.update_analysis(job.id, status="failed", error=message)
        db.record_event(user_id, "analysis_failed", doc_type=doc_type)
        job.publish({"stage": "error", "label": message, "progress": 100, "status": "failed"})
    finally:
        job.done = True
        with job.cond:
            job.cond.notify_all()


def submit(analysis_id: str, doc: db.DocumentRow, *, user_id: str, doc_type: str, perspective: str,
           jurisdiction: str, provider: Optional[LLMProvider], privacy_mode: bool, notices: List[str]) -> Job:
    _gc()
    job = Job(id=analysis_id)
    with _lock:
        _jobs[analysis_id] = job
    job.publish({"stage": "queued", "label": "Queued", "progress": 1, "status": "queued"})
    _executor.submit(_run, job, doc, user_id, doc_type, perspective, jurisdiction, provider, privacy_mode, notices)
    return job
