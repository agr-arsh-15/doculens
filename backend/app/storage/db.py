import hashlib
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DocumentRow(SQLModel, table=True):
    __tablename__ = "documents"
    id: str = Field(primary_key=True)
    content_hash: str = Field(index=True)
    filename: str
    source_type: str
    page_count: int = 0
    char_count: int = 0
    word_count: int = 0
    ocr_used: bool = False
    file_path: Optional[str] = None
    text: str
    pages_json: str = "[]"
    heading_hints_json: str = "[]"
    clauses_json: str = "[]"
    detection_json: str = "{}"
    warnings_json: str = "[]"
    created_at: str = Field(default_factory=utcnow)


class AnalysisRow(SQLModel, table=True):
    __tablename__ = "analyses"
    id: str = Field(primary_key=True)
    document_id: str = Field(index=True)
    cache_key: str = Field(index=True)
    status: str = "queued"
    error: Optional[str] = None
    filename: str = ""
    doc_type: Optional[str] = None
    doc_type_label: Optional[str] = None
    perspective: Optional[str] = None
    jurisdiction: Optional[str] = None
    overall: Optional[int] = None
    grade: Optional[str] = None
    finding_counts_json: str = "{}"
    engine_mode: Optional[str] = None
    result_json: Optional[str] = None
    lab_json: Optional[str] = None
    created_at: str = Field(default_factory=utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(engine, expire_on_commit=False)


def dumps(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif isinstance(value, list):
        value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
    return json.dumps(value, ensure_ascii=False)


def get_document(doc_id: str) -> Optional[DocumentRow]:
    with session() as s:
        return s.get(DocumentRow, doc_id)


def find_document_by_hash(content_hash: str) -> Optional[DocumentRow]:
    with session() as s:
        return s.exec(select(DocumentRow).where(DocumentRow.content_hash == content_hash)).first()


def save(row: SQLModel) -> None:
    with session() as s:
        s.add(row)
        s.commit()


def get_analysis(analysis_id: str) -> Optional[AnalysisRow]:
    with session() as s:
        return s.get(AnalysisRow, analysis_id)


def find_cached_analysis(cache_key: str) -> Optional[AnalysisRow]:
    with session() as s:
        stmt = (select(AnalysisRow).where(AnalysisRow.cache_key == cache_key, AnalysisRow.status == "completed")
                .order_by(AnalysisRow.created_at.desc()))
        return s.exec(stmt).first()


def update_analysis(analysis_id: str, **fields: Any) -> None:
    with session() as s:
        row = s.get(AnalysisRow, analysis_id)
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        s.add(row)
        s.commit()


def list_analyses(query: str = "", limit: int = 50) -> List[AnalysisRow]:
    with session() as s:
        stmt = select(AnalysisRow).where(AnalysisRow.status.in_(["completed", "running", "queued", "failed"]))
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                AnalysisRow.filename.ilike(like) | AnalysisRow.doc_type_label.ilike(like) | AnalysisRow.jurisdiction.ilike(like)
            )
        return list(s.exec(stmt.order_by(AnalysisRow.created_at.desc()).limit(limit)))


def delete_analysis(analysis_id: str) -> bool:
    with session() as s:
        row = s.get(AnalysisRow, analysis_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


def mark_interrupted() -> None:
    """Jobs run in-process; anything left running after a restart can never finish."""
    with session() as s:
        for row in s.exec(select(AnalysisRow).where(AnalysisRow.status.in_(["queued", "running"]))):
            row.status = "failed"
            row.error = "Server restarted before the analysis finished. Please run it again."
            s.add(row)
        s.commit()
