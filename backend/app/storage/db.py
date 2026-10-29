import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Index, UniqueConstraint, func
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

from app.config import DATABASE_URL  # noqa: F401  (re-exported for Alembic's env.py)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def day_start(days_ago: int = 0) -> str:
    """ISO timestamp of UTC midnight `days_ago` days back (timestamps are stored as ISO strings)."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (today - timedelta(days=days_ago)).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"
    id: str = Field(primary_key=True)
    email: str = Field(index=True)
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "user"
    status: str = "active"
    ai_daily_limit: Optional[int] = None
    llm_key_enc: Optional[str] = None
    llm_key_hint: Optional[str] = None
    created_at: str = Field(default_factory=utcnow, index=True)
    last_seen_at: str = Field(default_factory=utcnow, index=True)


class DocumentRow(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("user_id", "content_hash", name="uq_documents_user_hash"),)
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    content_hash: str = Field(index=True)
    filename: str
    source_type: str
    page_count: int = 0
    char_count: int = 0
    word_count: int = 0
    ocr_used: bool = False
    file_path: Optional[str] = None
    file_size: int = 0
    text: str
    pages_json: str = "[]"
    heading_hints_json: str = "[]"
    clauses_json: str = "[]"
    detection_json: str = "{}"
    warnings_json: str = "[]"
    created_at: str = Field(default_factory=utcnow)


class AnalysisRow(SQLModel, table=True):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_user_created", "user_id", "created_at"),)
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
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


class UsageEvent(SQLModel, table=True):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_user_kind_created", "user_id", "kind", "created_at"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    kind: str = Field(index=True)
    meta_json: str = "{}"
    created_at: str = Field(default_factory=utcnow, index=True)


class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"
    key: str = Field(primary_key=True)
    value: str


def init_db() -> None:
    from app.storage.migrations import upgrade

    upgrade(engine)


def session() -> Session:
    return Session(engine, expire_on_commit=False)


def dumps(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif isinstance(value, list):
        value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
    return json.dumps(value, ensure_ascii=False)


def save(row: SQLModel) -> None:
    with session() as s:
        s.add(row)
        s.commit()


# ---------- Documents (always scoped to a user) ----------

def get_document(doc_id: str, user_id: str) -> Optional[DocumentRow]:
    with session() as s:
        row = s.get(DocumentRow, doc_id)
        return row if row is not None and row.user_id == user_id else None


def find_document_by_hash(content_hash: str, user_id: str) -> Optional[DocumentRow]:
    with session() as s:
        stmt = select(DocumentRow).where(DocumentRow.user_id == user_id, DocumentRow.content_hash == content_hash)
        return s.exec(stmt).first()


# ---------- Analyses (always scoped to a user) ----------

def get_analysis(analysis_id: str, user_id: str) -> Optional[AnalysisRow]:
    with session() as s:
        row = s.get(AnalysisRow, analysis_id)
        return row if row is not None and row.user_id == user_id else None


def find_cached_analysis(cache_key: str, user_id: str) -> Optional[AnalysisRow]:
    """The user's own completed analysis for this key, else any user's (to be copied, never shared)."""
    with session() as s:
        base = select(AnalysisRow).where(AnalysisRow.cache_key == cache_key, AnalysisRow.status == "completed")
        own = s.exec(base.where(AnalysisRow.user_id == user_id).order_by(AnalysisRow.created_at.desc())).first()
        return own or s.exec(base.order_by(AnalysisRow.created_at.desc())).first()


def update_analysis(analysis_id: str, **fields: Any) -> None:
    with session() as s:
        row = s.get(AnalysisRow, analysis_id)
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        s.add(row)
        s.commit()


def list_analyses(user_id: str, query: str = "", limit: int = 50) -> List[AnalysisRow]:
    with session() as s:
        stmt = select(AnalysisRow).where(AnalysisRow.user_id == user_id,
                                         AnalysisRow.status.in_(["completed", "running", "queued", "failed"]))
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                func.lower(AnalysisRow.filename).like(like) | func.lower(AnalysisRow.doc_type_label).like(like)
                | func.lower(AnalysisRow.jurisdiction).like(like)
            )
        return list(s.exec(stmt.order_by(AnalysisRow.created_at.desc()).limit(limit)))


def delete_analysis(analysis_id: str, user_id: str) -> bool:
    with session() as s:
        row = s.get(AnalysisRow, analysis_id)
        if row is None or row.user_id != user_id:
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


# ---------- Profiles ----------

def get_profile(user_id: str) -> Optional[Profile]:
    with session() as s:
        return s.get(Profile, user_id)


def upsert_profile(user_id: str, email: str, name: Optional[str], avatar_url: Optional[str], role: str,
                   touch_after_seconds: int = 300) -> Profile:
    """Create or refresh a profile; last_seen_at is only written when it is older than a few minutes."""
    now = datetime.now(timezone.utc)
    with session() as s:
        row = s.get(Profile, user_id)
        if row is None:
            row = Profile(id=user_id, email=email, name=name, avatar_url=avatar_url, role=role)
            s.add(row)
            s.commit()
            return row
        changed = False
        for attr, value in (("email", email), ("name", name or row.name), ("avatar_url", avatar_url or row.avatar_url)):
            if getattr(row, attr) != value:
                setattr(row, attr, value)
                changed = True
        if role == "admin" and row.role != "admin":
            row.role, changed = "admin", True
        if now - datetime.fromisoformat(row.last_seen_at) > timedelta(seconds=touch_after_seconds):
            row.last_seen_at, changed = now.isoformat(), True
        if changed:
            s.add(row)
            s.commit()
        return row


def update_profile(user_id: str, **fields: Any) -> Optional[Profile]:
    with session() as s:
        row = s.get(Profile, user_id)
        if row is None:
            return None
        for k, v in fields.items():
            setattr(row, k, v)
        s.add(row)
        s.commit()
        return row


def delete_user_data(user_id: str) -> List[str]:
    """Remove every row owned by the user; returns the storage keys of their original files."""
    with session() as s:
        keys = [k for k in s.exec(select(DocumentRow.file_path).where(DocumentRow.user_id == user_id)) if k]
        s.exec(delete(AnalysisRow).where(AnalysisRow.user_id == user_id))
        s.exec(delete(DocumentRow).where(DocumentRow.user_id == user_id))
        s.exec(delete(UsageEvent).where(UsageEvent.user_id == user_id))
        s.exec(delete(Profile).where(Profile.id == user_id))
        s.commit()
        return keys


# ---------- Usage events and settings ----------

def record_event(user_id: str, kind: str, **meta: Any) -> None:
    save(UsageEvent(user_id=user_id, kind=kind, meta_json=json.dumps(meta) if meta else "{}"))


def count_events(user_id: str, kind: str, since: str) -> int:
    with session() as s:
        stmt = select(func.count()).select_from(UsageEvent).where(
            UsageEvent.user_id == user_id, UsageEvent.kind == kind, UsageEvent.created_at >= since)
        return int(s.exec(stmt).one())


def get_settings() -> Dict[str, str]:
    with session() as s:
        return {r.key: r.value for r in s.exec(select(AppSetting))}


def set_setting(key: str, value: str) -> None:
    with session() as s:
        row = s.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
        row.value = value
        s.add(row)
        s.commit()
