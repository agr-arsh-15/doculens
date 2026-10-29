import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.classify.detector import detect
from app.config import FILES_DIR, MAX_UPLOAD_MB
from app.ingestion.parser import DocumentParseError, parse_document
from app.models.schemas import Clause, Detection, DocumentDetail, DocumentOut, PageSpan, TextDocumentRequest
from app.storage import db
from app.structure.segmenter import segment_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

_MEDIA = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _out(row: db.DocumentRow) -> DocumentOut:
    return DocumentOut(
        id=row.id, filename=row.filename, source_type=row.source_type, page_count=row.page_count,
        char_count=row.char_count, word_count=row.word_count, ocr_used=row.ocr_used,
        has_original_file=bool(row.file_path and Path(row.file_path).exists()), created_at=row.created_at,
        detection=Detection.model_validate_json(row.detection_json), warnings=json.loads(row.warnings_json),
    )


def _safe_name(filename: str) -> str:
    name = Path(filename or "document.txt").name
    return re.sub(r"[^\w.\- ()]+", "_", name)[:120] or "document.txt"


def ingest_bytes(data: bytes, filename: str) -> db.DocumentRow:
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB:g} MB.")
    filename = _safe_name(filename)
    content_hash = db.sha256(data)
    existing = db.find_document_by_hash(content_hash)
    if existing is not None:
        return existing

    try:
        parsed = parse_document(data, filename)
    except DocumentParseError as exc:
        raise HTTPException(422, str(exc)) from exc
    clauses = segment_document(parsed.text, parsed.pages, parsed.heading_hints)
    detection = detect(parsed.text)

    doc_id = uuid.uuid4().hex[:16]
    file_path = None
    ext = Path(filename).suffix.lower()
    if parsed.source_type in ("pdf", "docx") and ext in _MEDIA:
        path = FILES_DIR / f"{doc_id}{ext}"
        path.write_bytes(data)
        file_path = str(path)

    row = db.DocumentRow(
        id=doc_id, content_hash=content_hash, filename=filename, source_type=parsed.source_type,
        page_count=parsed.page_count, char_count=len(parsed.text), word_count=len(parsed.text.split()),
        ocr_used=parsed.ocr_used, file_path=file_path, text=parsed.text, pages_json=db.dumps(parsed.pages),
        heading_hints_json=json.dumps(parsed.heading_hints), clauses_json=db.dumps(clauses),
        detection_json=detection.model_dump_json(), warnings_json=json.dumps(parsed.warnings),
    )
    db.save(row)
    return row


@router.post("", response_model=DocumentOut)
async def upload_document(file: UploadFile = File(...)):
    data = await file.read()
    row = await run_in_threadpool(ingest_bytes, data, file.filename or "document")
    return _out(row)


@router.post("/text", response_model=DocumentOut)
def create_text_document(req: TextDocumentRequest):
    text = (req.text or "").strip()
    if len(text) < 80:
        raise HTTPException(400, "Paste at least a few sentences of the document.")
    name = _safe_name(req.filename or "pasted-text.txt")
    if not name.lower().endswith((".txt", ".md")):
        name += ".txt"
    return _out(ingest_bytes(text.encode("utf-8"), name))


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str):
    row = db.get_document(doc_id)
    if row is None:
        raise HTTPException(404, "Document not found.")
    base = _out(row)
    return DocumentDetail(
        **base.model_dump(), text=row.text,
        pages=[PageSpan.model_validate(p) for p in json.loads(row.pages_json)],
        clauses=[Clause.model_validate(c) for c in json.loads(row.clauses_json)],
    )


@router.get("/{doc_id}/file")
def get_original_file(doc_id: str):
    row = db.get_document(doc_id)
    if row is None or not row.file_path or not Path(row.file_path).exists():
        raise HTTPException(404, "Original file is not available for this document.")
    ext = Path(row.file_path).suffix.lower()
    return FileResponse(row.file_path, media_type=_MEDIA.get(ext, "application/octet-stream"), filename=row.filename)


def document_out(row: db.DocumentRow) -> DocumentOut:
    return _out(row)
