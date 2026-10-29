import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.auth import CurrentUser, current_user
from app.classify.detector import detect
from app.config import MAX_UPLOAD_MB, RATE_LIMIT_UPLOADS
from app.ingestion.parser import DocumentParseError, parse_document
from app.models.schemas import Clause, Detection, DocumentDetail, DocumentOut, PageSpan, TextDocumentRequest
from app.security import limiter, sniff_upload
from app.storage import db
from app.storage.files import StorageError, object_key, storage
from app.structure.segmenter import segment_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

_MEDIA = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _out(row: db.DocumentRow) -> DocumentOut:
    return DocumentOut(
        id=row.id, filename=row.filename, source_type=row.source_type, page_count=row.page_count,
        char_count=row.char_count, word_count=row.word_count, ocr_used=row.ocr_used,
        has_original_file=bool(row.file_path), created_at=row.created_at,
        detection=Detection.model_validate_json(row.detection_json), warnings=json.loads(row.warnings_json),
    )


def _safe_name(filename: str) -> str:
    name = Path(filename or "document.txt").name
    return re.sub(r"[^\w.\- ()]+", "_", name)[:120] or "document.txt"


def ingest_bytes(data: bytes, filename: str, user_id: str) -> db.DocumentRow:
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB:g} MB.")
    filename = _safe_name(filename)
    sniff_upload(data, filename)
    content_hash = db.sha256(data)
    existing = db.find_document_by_hash(content_hash, user_id)
    if existing is not None:
        return existing

    try:
        parsed = parse_document(data, filename)
    except DocumentParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    clauses = segment_document(parsed.text, parsed.pages, parsed.heading_hints)
    detection = detect(parsed.text)

    doc_id = uuid.uuid4().hex[:16]
    file_key = None
    ext = Path(filename).suffix.lower()
    if parsed.source_type in ("pdf", "docx") and ext in _MEDIA:
        file_key = object_key(user_id, doc_id, ext)
        try:
            storage().put(file_key, data, _MEDIA[ext])
        except StorageError as exc:
            raise HTTPException(503, "Could not store the file right now. Please try again.") from exc

    row = db.DocumentRow(
        id=doc_id, user_id=user_id, content_hash=content_hash, filename=filename, source_type=parsed.source_type,
        page_count=parsed.page_count, char_count=len(parsed.text), word_count=len(parsed.text.split()),
        ocr_used=parsed.ocr_used, file_path=file_key, file_size=len(data) if file_key else 0, text=parsed.text,
        pages_json=db.dumps(parsed.pages), heading_hints_json=json.dumps(parsed.heading_hints),
        clauses_json=db.dumps(clauses), detection_json=detection.model_dump_json(),
        warnings_json=json.dumps(parsed.warnings),
    )
    db.save(row)
    db.record_event(user_id, "upload", source_type=parsed.source_type, doc_type=detection.doc_type)
    return row


@router.post("", response_model=DocumentOut)
@limiter.limit(RATE_LIMIT_UPLOADS)
async def upload_document(request: Request, file: UploadFile = File(...), user: CurrentUser = Depends(current_user)):
    data = await file.read(int(MAX_UPLOAD_MB * 1024 * 1024) + 1)
    row = await run_in_threadpool(ingest_bytes, data, file.filename or "document", user.id)
    return _out(row)


@router.post("/text", response_model=DocumentOut)
@limiter.limit(RATE_LIMIT_UPLOADS)
def create_text_document(request: Request, req: TextDocumentRequest, user: CurrentUser = Depends(current_user)):
    text = (req.text or "").strip()
    if len(text) < 80:
        raise HTTPException(400, "Paste at least a few sentences of the document.")
    name = _safe_name(req.filename or "pasted-text.txt")
    if not name.lower().endswith((".txt", ".md")):
        name += ".txt"
    return _out(ingest_bytes(text.encode("utf-8"), name, user.id))


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str, user: CurrentUser = Depends(current_user)):
    row = db.get_document(doc_id, user.id)
    if row is None:
        raise HTTPException(404, "Document not found.")
    base = _out(row)
    return DocumentDetail(
        **base.model_dump(), text=row.text,
        pages=[PageSpan.model_validate(p) for p in json.loads(row.pages_json)],
        clauses=[Clause.model_validate(c) for c in json.loads(row.clauses_json)],
    )


@router.get("/{doc_id}/file")
def get_original_file(doc_id: str, user: CurrentUser = Depends(current_user)):
    row = db.get_document(doc_id, user.id)
    data = None
    if row is not None and row.file_path:
        try:
            data = storage().get(row.file_path)
        except StorageError as exc:
            raise HTTPException(503, "Could not load the original file right now.") from exc
    if data is None:
        raise HTTPException(404, "Original file is not available for this document.")
    ext = Path(row.file_path).suffix.lower()
    return Response(data, media_type=_MEDIA.get(ext, "application/octet-stream"),
                    headers={"Content-Disposition": f'inline; filename="{row.filename}"', "Cache-Control": "private, no-store"})


def document_out(row: db.DocumentRow) -> DocumentOut:
    return _out(row)
