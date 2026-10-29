import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import config, usage
from app.auth import CurrentUser, current_user, delete_auth_user
from app.llm.provider import LLMError, LLMFatalError, user_provider, validate_key
from app.security import limiter
from app.storage import db
from app.storage.files import storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/me", tags=["account"])


class UsageOut(BaseModel):
    ai_analyses_used: int
    ai_analyses_limit: int
    chat_messages_used: int
    chat_messages_limit: int
    ai_enabled: bool


class MeOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    created_at: str
    has_own_key: bool
    own_key_hint: Optional[str] = None
    usage: UsageOut
    auth_mode: str


class KeyIn(BaseModel):
    api_key: str = Field(min_length=20, max_length=200)


def _me(user_id: str) -> MeOut:
    profile = db.get_profile(user_id)
    current = usage.settings()
    today = usage.usage_today(user_id)
    return MeOut(
        id=profile.id, email=profile.email, name=profile.name, avatar_url=profile.avatar_url, role=profile.role,
        created_at=profile.created_at, has_own_key=bool(profile.llm_key_enc), own_key_hint=profile.llm_key_hint,
        auth_mode=config.AUTH_MODE,
        usage=UsageOut(ai_analyses_used=today["ai_analyses"], ai_analyses_limit=usage.ai_limit_for(profile, current),
                       chat_messages_used=today["chat_messages"], chat_messages_limit=current.chat_daily_limit,
                       ai_enabled=current.ai_enabled),
    )


@router.get("", response_model=MeOut)
def me(user: CurrentUser = Depends(current_user)):
    return _me(user.id)


@router.put("/llm-key", response_model=MeOut)
@limiter.limit("5/minute")
def set_llm_key(request: Request, body: KeyIn, user: CurrentUser = Depends(current_user)):
    raw = body.api_key.strip()
    if not raw.startswith("gsk_"):
        raise HTTPException(400, "That does not look like a Groq API key (it should start with gsk_).")
    try:
        validate_key(user_provider(raw))
    except LLMFatalError as exc:
        raise HTTPException(400, "Groq rejected this key. Check that it is active and copied in full.") from exc
    except LLMError as exc:
        log.info("Key validation inconclusive: %s", type(exc).__name__)
        raise HTTPException(502, "Could not reach Groq to check the key. Try again in a minute.") from exc
    db.update_profile(user.id, llm_key_enc=usage.encrypt_key(raw), llm_key_hint=usage.key_hint(raw))
    db.record_event(user.id, "own_key_added")
    return _me(user.id)


@router.delete("/llm-key", response_model=MeOut)
def delete_llm_key(user: CurrentUser = Depends(current_user)):
    db.update_profile(user.id, llm_key_enc=None, llm_key_hint=None)
    return _me(user.id)


@router.delete("")
def delete_account(user: CurrentUser = Depends(current_user)):
    if config.AUTH_MODE == "local":
        raise HTTPException(400, "The local account cannot be deleted. Delete analyses from History instead.")
    delete_auth_user(user.id)
    keys = db.delete_user_data(user.id)
    try:
        storage().delete(keys)
    except Exception:  # the account is already gone; leftover files are cleaned up by key prefix later
        log.exception("Could not delete %d stored files for a deleted account", len(keys))
    return {"deleted": True}
