import asyncio
import hashlib
import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app import jobs, usage
from app.analysis.chat import answer_question
from app.analysis.compare import compare_analyses
from app.analysis.negotiation import build_negotiation_email
from app.auth import CurrentUser, current_user
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.config import PROMPT_VERSION, RATE_LIMIT_ANALYSES, RATE_LIMIT_CHAT
from app.lab.runner import run_lab
from app.lab.schemas import LabResult
from app.models.schemas import (
    AnalysisRequest, AnalysisResult, AnalysisStatus, AnalysisSummary, ChatRequest, ChatResponse, CompareRequest,
    CompareResult, Detection, NegotiationEmailRequest, NegotiationEmailResponse,
)
from app.playbooks.loader import get_playbook, load_playbooks
from app.reports.pdf import build_report_pdf
from app.security import limiter
from app.storage import db

router = APIRouter(prefix="/api", tags=["analyses"])


def _cache_key(doc: db.DocumentRow, doc_type: str, perspective: str, jurisdiction: str, provider, privacy: bool) -> str:
    mode = f"{provider.name}:{provider.model}" if provider else "local"
    raw = "|".join([doc.content_hash, doc_type, perspective, jurisdiction, mode, str(privacy),
                    get_playbook(doc_type).version, PROMPT_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def _status(row: db.AnalysisRow, cached: bool = False) -> AnalysisStatus:
    return AnalysisStatus(id=row.id, document_id=row.document_id, status=row.status, error=row.error, cached=cached)


def _owned(analysis_id: str, user: CurrentUser) -> db.AnalysisRow:
    row = db.get_analysis(analysis_id, user.id)
    if row is None:
        raise HTTPException(404, "Analysis not found.")
    return row


def _load_result(analysis_id: str, user: CurrentUser) -> AnalysisResult:
    row = _owned(analysis_id, user)
    if row.status != "completed" or not row.result_json:
        raise HTTPException(409, f"Analysis is {row.status}." + (f" {row.error}" if row.error else ""))
    return AnalysisResult.model_validate_json(row.result_json)


def _copy_for_user(source: db.AnalysisRow, doc: db.DocumentRow, user: CurrentUser) -> db.AnalysisRow:
    """Reuse another user's identical result as a private copy: same content and settings, new owner and ids."""
    new_id = uuid.uuid4().hex[:16]
    result = AnalysisResult.model_validate_json(source.result_json)
    result.analysis_id, result.document_id, result.filename = new_id, doc.id, doc.filename
    row = db.AnalysisRow(
        id=new_id, user_id=user.id, document_id=doc.id, cache_key=source.cache_key, status="completed",
        filename=doc.filename, doc_type=source.doc_type, doc_type_label=source.doc_type_label,
        perspective=source.perspective, jurisdiction=source.jurisdiction, overall=source.overall, grade=source.grade,
        finding_counts_json=source.finding_counts_json, engine_mode=source.engine_mode,
        result_json=result.model_dump_json(),
    )
    db.save(row)
    return row


@router.post("/analyses", response_model=AnalysisStatus)
@limiter.limit(RATE_LIMIT_ANALYSES)
def create_analysis(request: Request, req: AnalysisRequest, user: CurrentUser = Depends(current_user)):
    doc = db.get_document(req.document_id, user.id)
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

    profile = db.get_profile(user.id)
    plan = usage.plan_analysis(profile, req.use_llm)
    key = _cache_key(doc, doc_type, perspective, jurisdiction, plan.provider, req.privacy_mode)
    if not req.force:
        cached = db.find_cached_analysis(key, user.id)
        if cached is not None:
            row = cached if cached.user_id == user.id else _copy_for_user(cached, doc, user)
            db.record_event(user.id, "analysis", cached=True, doc_type=doc_type, jurisdiction=jurisdiction,
                            mode=row.engine_mode)
            return _status(row, cached=True)

    analysis_id = uuid.uuid4().hex[:16]
    db.save(db.AnalysisRow(id=analysis_id, user_id=user.id, document_id=doc.id, cache_key=key, status="queued",
                           filename=doc.filename, doc_type=doc_type, doc_type_label=get_playbook(doc_type).name,
                           perspective=perspective, jurisdiction=jurisdiction))
    if plan.counts_against_quota:
        db.record_event(user.id, "ai_analysis", analysis_id=analysis_id)
    jobs.submit(analysis_id, doc, user_id=user.id, doc_type=doc_type, perspective=perspective,
                jurisdiction=jurisdiction, provider=plan.provider, privacy_mode=req.privacy_mode,
                notices=[plan.notice] if plan.notice else [])
    return AnalysisStatus(id=analysis_id, document_id=doc.id, status="queued")


@router.get("/analyses", response_model=List[AnalysisSummary])
def list_analyses(q: str = Query("", max_length=100), limit: int = Query(50, ge=1, le=200),
                  user: CurrentUser = Depends(current_user)):
    return [
        AnalysisSummary(
            id=r.id, document_id=r.document_id, filename=r.filename, status=r.status, doc_type=r.doc_type,
            doc_type_label=r.doc_type_label, perspective=r.perspective, jurisdiction=r.jurisdiction, overall=r.overall,
            grade=r.grade, finding_counts=json.loads(r.finding_counts_json or "{}"), engine_mode=r.engine_mode,
            created_at=r.created_at,
        )
        for r in db.list_analyses(user.id, q, limit)
    ]


@router.get("/analyses/{analysis_id}/status", response_model=AnalysisStatus)
def analysis_status(analysis_id: str, user: CurrentUser = Depends(current_user)):
    return _status(_owned(analysis_id, user))


@router.get("/analyses/{analysis_id}/events")
async def analysis_events(analysis_id: str, request: Request, user: CurrentUser = Depends(current_user)):
    _owned(analysis_id, user)

    def sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    async def stream():
        job = jobs.get_job(analysis_id)
        if job is None:
            final = db.get_analysis(analysis_id, user.id)
            if final is not None and final.status == "completed":
                yield sse({"stage": "done", "label": "Analysis complete", "progress": 100, "status": "completed"})
            else:
                label = (final.error if final else None) or "Analysis is not running."
                yield sse({"stage": "error", "label": label, "progress": 100, "status": "failed"})
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
def get_analysis(analysis_id: str, user: CurrentUser = Depends(current_user)):
    return _load_result(analysis_id, user)


@router.delete("/analyses/{analysis_id}")
def delete_analysis(analysis_id: str, user: CurrentUser = Depends(current_user)):
    if not db.delete_analysis(analysis_id, user.id):
        raise HTTPException(404, "Analysis not found.")
    return {"deleted": analysis_id}


@router.post("/analyses/{analysis_id}/chat", response_model=ChatResponse)
@limiter.limit(RATE_LIMIT_CHAT)
def chat(request: Request, analysis_id: str, req: ChatRequest, user: CurrentUser = Depends(current_user)):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question about the document.")
    result = _load_result(analysis_id, user)
    plan = usage.plan_chat(db.get_profile(user.id))
    response = answer_question(result, question[:1000], req.history, provider=plan.provider, notice=plan.notice)
    db.record_event(user.id, "chat")
    if response.mode == "llm" and plan.counts_against_quota:
        db.record_event(user.id, "chat_ai")
    return response


@router.post("/analyses/{analysis_id}/negotiation-email", response_model=NegotiationEmailResponse)
@limiter.limit(RATE_LIMIT_CHAT)
def negotiation_email(request: Request, analysis_id: str, req: NegotiationEmailRequest,
                      user: CurrentUser = Depends(current_user)):
    return build_negotiation_email(_load_result(analysis_id, user), req.finding_ids, req.recipient, req.tone)


@router.get("/analyses/{analysis_id}/report.pdf")
def report_pdf(analysis_id: str, user: CurrentUser = Depends(current_user)):
    result = _load_result(analysis_id, user)
    stem = "".join(ch for ch in result.filename.rsplit(".", 1)[0][:60] if ch.isalnum() or ch in " -_") or "document"
    db.record_event(user.id, "pdf_export")
    return Response(build_report_pdf(result), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="DocuLens-{stem}.pdf"'})


@router.get("/analyses/{analysis_id}/lab", response_model=LabResult)
async def lab(analysis_id: str, user: CurrentUser = Depends(current_user)):
    row = _owned(analysis_id, user)
    db.record_event(user.id, "lab")
    if row.lab_json:
        return LabResult.model_validate_json(row.lab_json)
    result = _load_result(analysis_id, user)
    doc = db.get_document(result.document_id, user.id)
    if doc is None:
        raise HTTPException(404, "Source document no longer exists.")
    detection = Detection.model_validate_json(doc.detection_json)
    lab_result = await run_in_threadpool(run_lab, doc.text, result, detection)
    db.update_analysis(analysis_id, lab_json=lab_result.model_dump_json())
    return lab_result


@router.post("/compare", response_model=CompareResult)
def compare(req: CompareRequest, user: CurrentUser = Depends(current_user)):
    if req.analysis_a == req.analysis_b:
        raise HTTPException(400, "Pick two different analyses to compare.")
    db.record_event(user.id, "compare")
    return compare_analyses(_load_result(req.analysis_a, user), _load_result(req.analysis_b, user))

