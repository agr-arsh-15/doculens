import asyncio
import hashlib
import json
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app import jobs
from app.analysis.chat import answer_question
from app.analysis.compare import compare_analyses
from app.analysis.negotiation import build_negotiation_email
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.config import PROMPT_VERSION
from app.lab.runner import run_lab
from app.lab.schemas import LabResult
from app.llm.provider import get_provider
from app.models.schemas import (
    AnalysisRequest, AnalysisResult, AnalysisStatus, AnalysisSummary, ChatRequest, ChatResponse, CompareRequest,
    CompareResult, Detection, NegotiationEmailRequest, NegotiationEmailResponse,
)
from app.playbooks.loader import get_playbook, load_playbooks
from app.reports.pdf import build_report_pdf
from app.storage import db

router = APIRouter(prefix="/api", tags=["analyses"])


def _cache_key(doc: db.DocumentRow, doc_type: str, perspective: str, jurisdiction: str, use_llm: bool, privacy: bool) -> str:
    provider = get_provider() if use_llm else None
    mode = f"{provider.name}:{provider.model}" if provider else "local"
    raw = "|".join([doc.content_hash, doc_type, perspective, jurisdiction, mode, str(privacy),
                    get_playbook(doc_type).version, PROMPT_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def _status(row: db.AnalysisRow, cached: bool = False) -> AnalysisStatus:
    return AnalysisStatus(id=row.id, document_id=row.document_id, status=row.status, error=row.error, cached=cached)


def _load_result(analysis_id: str) -> AnalysisResult:
    row = db.get_analysis(analysis_id)
    if row is None:
        raise HTTPException(404, "Analysis not found.")
    if row.status != "completed" or not row.result_json:
        raise HTTPException(409, f"Analysis is {row.status}." + (f" {row.error}" if row.error else ""))
    return AnalysisResult.model_validate_json(row.result_json)


@router.post("/analyses", response_model=AnalysisStatus)
def create_analysis(req: AnalysisRequest):
    doc = db.get_document(req.document_id)
    if doc is None:
        raise HTTPException(404, "Document not found. Upload it again.")
    detection = Detection.model_validate_json(doc.detection_json)
    doc_type = req.doc_type or detection.doc_type
    if doc_type not in load_playbooks():
        raise HTTPException(400, f"Unknown document type '{doc_type}'.")
    jurisdiction = req.jurisdiction or detection.jurisdiction
    if jurisdiction not in JURISDICTION_LABELS:
        raise HTTPException(400, f"Unknown jurisdiction '{jurisdiction}'.")
    perspective = get_playbook(doc_type).perspective(req.perspective).id

    key = _cache_key(doc, doc_type, perspective, jurisdiction, req.use_llm, req.privacy_mode)
    if not req.force:
        cached = db.find_cached_analysis(key)
        if cached is not None:
            return _status(cached, cached=True)

    analysis_id = uuid.uuid4().hex[:16]
    db.save(db.AnalysisRow(id=analysis_id, document_id=doc.id, cache_key=key, status="queued", filename=doc.filename,
                           doc_type=doc_type, doc_type_label=get_playbook(doc_type).name, perspective=perspective,
                           jurisdiction=jurisdiction))
    jobs.submit(analysis_id, doc, doc_type=doc_type, perspective=perspective, jurisdiction=jurisdiction,
                use_llm=req.use_llm, privacy_mode=req.privacy_mode)
    return AnalysisStatus(id=analysis_id, document_id=doc.id, status="queued")


@router.get("/analyses", response_model=List[AnalysisSummary])
def list_analyses(q: str = Query("", max_length=100), limit: int = Query(50, ge=1, le=200)):
    return [
        AnalysisSummary(
            id=r.id, document_id=r.document_id, filename=r.filename, status=r.status, doc_type=r.doc_type,
            doc_type_label=r.doc_type_label, perspective=r.perspective, jurisdiction=r.jurisdiction, overall=r.overall,
            grade=r.grade, finding_counts=json.loads(r.finding_counts_json or "{}"), engine_mode=r.engine_mode,
            created_at=r.created_at,
        )
        for r in db.list_analyses(q, limit)
    ]


@router.get("/analyses/{analysis_id}/status", response_model=AnalysisStatus)
def analysis_status(analysis_id: str):
    row = db.get_analysis(analysis_id)
    if row is None:
        raise HTTPException(404, "Analysis not found.")
    return _status(row)


@router.get("/analyses/{analysis_id}/events")
async def analysis_events(analysis_id: str, request: Request):
    row = db.get_analysis(analysis_id)
    if row is None:
        raise HTTPException(404, "Analysis not found.")

    def sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    async def stream():
        job = jobs.get_job(analysis_id)
        if job is None:
            final = db.get_analysis(analysis_id)
            if final.status == "completed":
                yield sse({"stage": "done", "label": "Analysis complete", "progress": 100, "status": "completed"})
            else:
                yield sse({"stage": "error", "label": final.error or "Analysis is not running.", "progress": 100, "status": "failed"})
            return
        sent, idle = 0, 0.0
        while True:
            if await request.is_disconnected():
                return
            events = job.events[sent:]
            for e in events:
                yield sse(e)
            sent += len(events)
            if job.done and sent >= len(job.events):
                return
            await asyncio.sleep(0.25)
            idle = 0.0 if events else idle + 0.25
            if idle >= 10:
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/analyses/{analysis_id}", response_model=AnalysisResult)
def get_analysis(analysis_id: str):
    return _load_result(analysis_id)


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str):
    if not db.delete_analysis(analysis_id):
        raise HTTPException(404, "Analysis not found.")
    return {"deleted": analysis_id}


@router.post("/analyses/{analysis_id}/chat", response_model=ChatResponse)
def chat(analysis_id: str, req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question about the document.")
    return answer_question(_load_result(analysis_id), question[:1000], req.history)


@router.post("/analyses/{analysis_id}/negotiation-email", response_model=NegotiationEmailResponse)
def negotiation_email(analysis_id: str, req: NegotiationEmailRequest):
    return build_negotiation_email(_load_result(analysis_id), req.finding_ids, req.recipient, req.tone)


@router.get("/analyses/{analysis_id}/report.pdf")
def report_pdf(analysis_id: str):
    result = _load_result(analysis_id)
    stem = result.filename.rsplit(".", 1)[0][:60] or "document"
    return Response(build_report_pdf(result), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="DocuLens-{stem}.pdf"'})


@router.get("/analyses/{analysis_id}/lab", response_model=LabResult)
async def lab(analysis_id: str):
    row = db.get_analysis(analysis_id)
    if row is not None and row.lab_json:
        return LabResult.model_validate_json(row.lab_json)
    result = _load_result(analysis_id)
    doc = db.get_document(result.document_id)
    if doc is None:
        raise HTTPException(404, "Source document no longer exists.")
    detection = Detection.model_validate_json(doc.detection_json)
    lab_result = await run_in_threadpool(run_lab, doc.text, result, detection)
    db.update_analysis(analysis_id, lab_json=lab_result.model_dump_json())
    return lab_result


@router.post("/compare", response_model=CompareResult)
def compare(req: CompareRequest):
    if req.analysis_a == req.analysis_b:
        raise HTTPException(400, "Pick two different analyses to compare.")
    return compare_analyses(_load_result(req.analysis_a), _load_result(req.analysis_b))
