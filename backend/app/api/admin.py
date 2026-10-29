"""Administrator dashboard: aggregate KPIs and account controls. Never returns document text or findings."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import select

from app import usage
from app.auth import CurrentUser, require_admin
from app.storage import db

router = APIRouter(prefix="/api/admin", tags=["admin"])


class DayPoint(BaseModel):
    day: str
    signups: int = 0
    analyses: int = 0
    ai_analyses: int = 0


class Kpis(BaseModel):
    users_total: int
    users_new_7d: int
    users_new_30d: int
    users_active_today: int
    users_active_7d: int
    users_blocked: int
    users_with_own_key: int
    analyses_total: int
    analyses_today: int
    analyses_ai: int
    analyses_local: int
    analyses_failed: int
    llm_fallbacks_30d: int
    chats_30d: int
    pdf_exports_30d: int
    average_score: Optional[float] = None
    storage_bytes: int
    documents_total: int
    doc_types: Dict[str, int]
    jurisdictions: Dict[str, int]
    grades: Dict[str, int]
    daily: List[DayPoint]


class AdminUser(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    role: str
    status: str
    created_at: str
    last_seen_at: str
    analyses: int
    ai_used_today: int
    ai_daily_limit: int
    limit_overridden: bool
    has_own_key: bool


class UserPage(BaseModel):
    total: int
    users: List[AdminUser]


class UserPatch(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|blocked)$")
    ai_daily_limit: Optional[int] = Field(None, ge=0, le=1000)
    reset_limit: bool = False


class SettingsIO(BaseModel):
    default_ai_daily_limit: int = Field(ge=0, le=1000)
    chat_daily_limit: int = Field(ge=0, le=10000)
    ai_enabled: bool


def _since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@router.get("/kpis", response_model=Kpis)
def kpis(_: CurrentUser = Depends(require_admin)):
    today, d7, d30 = db.day_start(), _since(7), _since(30)
    with db.session() as s:
        def count(model, *where) -> int:
            return int(s.exec(select(func.count()).select_from(model).where(*where)).one())

        P, A, D, E = db.Profile, db.AnalysisRow, db.DocumentRow, db.UsageEvent
        completed = list(s.exec(select(A.doc_type, A.jurisdiction, A.grade, A.overall, A.engine_mode)
                                .where(A.status == "completed")))
        recent = list(s.exec(select(E.kind, E.created_at).where(E.created_at >= db.day_start(29),
                                                                E.kind.in_(["analysis", "ai_analysis"]))))
        signups = list(s.exec(select(P.created_at).where(P.created_at >= db.day_start(29))))
        out = dict(
            users_total=count(P), users_new_7d=count(P, P.created_at >= d7), users_new_30d=count(P, P.created_at >= d30),
            users_active_today=count(P, P.last_seen_at >= today), users_active_7d=count(P, P.last_seen_at >= d7),
            users_blocked=count(P, P.status == "blocked"), users_with_own_key=count(P, P.llm_key_enc.is_not(None)),
            analyses_total=len(completed), analyses_today=count(A, A.created_at >= today, A.status == "completed"),
            analyses_failed=count(A, A.status == "failed"),
            llm_fallbacks_30d=count(E, E.kind == "llm_fallback", E.created_at >= d30),
            chats_30d=count(E, E.kind == "chat", E.created_at >= d30),
            pdf_exports_30d=count(E, E.kind == "pdf_export", E.created_at >= d30),
            storage_bytes=int(s.exec(select(func.coalesce(func.sum(D.file_size), 0))).one()),
            documents_total=count(D),
        )
    scores = [r.overall for r in completed if r.overall is not None]
    daily: Dict[str, DayPoint] = {}
    for i in range(29, -1, -1):
        day = db.day_start(i)[:10]
        daily[day] = DayPoint(day=day)
    for created in signups:
        if created[:10] in daily:
            daily[created[:10]].signups += 1
    for kind, created in recent:
        point = daily.get(created[:10])
        if point is not None:
            if kind == "analysis":
                point.analyses += 1
            else:
                point.ai_analyses += 1
    return Kpis(
        **out,
        analyses_ai=sum(1 for r in completed if r.engine_mode == "hybrid"),
        analyses_local=sum(1 for r in completed if r.engine_mode != "hybrid"),
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
        doc_types=dict(Counter(r.doc_type for r in completed if r.doc_type).most_common()),
        jurisdictions=dict(Counter(r.jurisdiction for r in completed if r.jurisdiction).most_common()),
        grades=dict(sorted(Counter(r.grade for r in completed if r.grade).items())),
        daily=list(daily.values()),
    )


def _admin_users(s, rows: List[db.Profile]) -> List[AdminUser]:
    current = usage.settings()
    ids = [r.id for r in rows]
    analyses = defaultdict(int, {uid: n for uid, n in s.exec(
        select(db.AnalysisRow.user_id, func.count()).where(db.AnalysisRow.user_id.in_(ids),
                                                           db.AnalysisRow.status == "completed")
        .group_by(db.AnalysisRow.user_id))})
    ai_today = defaultdict(int, {uid: n for uid, n in s.exec(
        select(db.UsageEvent.user_id, func.count()).where(db.UsageEvent.user_id.in_(ids),
                                                          db.UsageEvent.kind == "ai_analysis",
                                                          db.UsageEvent.created_at >= db.day_start())
        .group_by(db.UsageEvent.user_id))})
    return [
        AdminUser(id=r.id, email=r.email, name=r.name, role=r.role, status=r.status, created_at=r.created_at,
                  last_seen_at=r.last_seen_at, analyses=analyses[r.id], ai_used_today=ai_today[r.id],
                  ai_daily_limit=usage.ai_limit_for(r, current), limit_overridden=r.ai_daily_limit is not None,
                  has_own_key=bool(r.llm_key_enc))
        for r in rows
    ]


@router.get("/users", response_model=UserPage)
def users(q: str = Query("", max_length=100), offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
          _: CurrentUser = Depends(require_admin)):
    with db.session() as s:
        P = db.Profile
        stmt = select(P)
        if q:
            like = f"%{q.lower()}%"
            stmt = stmt.where(func.lower(P.email).like(like) | func.lower(func.coalesce(P.name, "")).like(like))
        total = int(s.exec(select(func.count()).select_from(stmt.subquery())).one())
        rows = list(s.exec(stmt.order_by(P.created_at.desc()).offset(offset).limit(limit)))
        return UserPage(total=total, users=_admin_users(s, rows))


@router.patch("/users/{user_id}", response_model=AdminUser)
def update_user(user_id: str, patch: UserPatch, admin: CurrentUser = Depends(require_admin)):
    target = db.get_profile(user_id)
    if target is None:
        raise HTTPException(404, "User not found.")
    fields = {}
    if patch.status is not None:
        if target.role == "admin" and patch.status == "blocked":
            raise HTTPException(400, "Administrators cannot be blocked.")
        fields["status"] = patch.status
    if patch.reset_limit:
        fields["ai_daily_limit"] = None
    elif patch.ai_daily_limit is not None:
        fields["ai_daily_limit"] = patch.ai_daily_limit
    if fields:
        db.update_profile(user_id, **fields)
        db.record_event(admin.id, "admin_update_user", target=user_id, fields=sorted(fields))
    with db.session() as s:
        return _admin_users(s, [db.get_profile(user_id)])[0]


@router.get("/settings", response_model=SettingsIO)
def get_settings(_: CurrentUser = Depends(require_admin)):
    current = usage.settings()
    return SettingsIO(**current.__dict__)


@router.put("/settings", response_model=SettingsIO)
def put_settings(body: SettingsIO, admin: CurrentUser = Depends(require_admin)):
    saved = usage.save_settings(usage.Settings(**body.model_dump()))
    db.record_event(admin.id, "admin_update_settings")
    return SettingsIO(**saved.__dict__)
