"""Daily quotas on the server's LLM key, users' own (encrypted) keys, and global settings."""
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app import config
from app.llm.provider import LLMProvider, get_provider, user_provider
from app.storage import db

SETTING_AI_LIMIT = "default_ai_daily_limit"
SETTING_CHAT_LIMIT = "chat_daily_limit"
SETTING_AI_ENABLED = "ai_enabled"


@dataclass
class Settings:
    default_ai_daily_limit: int
    chat_daily_limit: int
    ai_enabled: bool


def settings() -> Settings:
    raw = db.get_settings()
    return Settings(
        default_ai_daily_limit=int(raw.get(SETTING_AI_LIMIT, config.DEFAULT_AI_DAILY_LIMIT)),
        chat_daily_limit=int(raw.get(SETTING_CHAT_LIMIT, config.DEFAULT_CHAT_DAILY_LIMIT)),
        ai_enabled=raw.get(SETTING_AI_ENABLED, "true") == "true",
    )


def save_settings(new: Settings) -> Settings:
    db.set_setting(SETTING_AI_LIMIT, str(new.default_ai_daily_limit))
    db.set_setting(SETTING_CHAT_LIMIT, str(new.chat_daily_limit))
    db.set_setting(SETTING_AI_ENABLED, "true" if new.ai_enabled else "false")
    return settings()


# ---------- Encryption of users' own API keys ----------

@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if config.ENCRYPTION_KEY:
        return Fernet(config.ENCRYPTION_KEY.encode())
    # Development only (production requires ENCRYPTION_KEY): a key kept next to the local database.
    path = config.DATA_DIR / "encryption.key"
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
        path.chmod(0o600)
    return Fernet(path.read_bytes().strip())


def encrypt_key(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_key(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def key_hint(raw: str) -> str:
    return f"{raw[:4]}...{raw[-4:]}" if len(raw) > 12 else "set"


# ---------- Quotas ----------

def ai_limit_for(profile: db.Profile, current: Optional[Settings] = None) -> int:
    current = current or settings()
    return profile.ai_daily_limit if profile.ai_daily_limit is not None else current.default_ai_daily_limit


def usage_today(user_id: str) -> dict:
    since = db.day_start()
    return {"ai_analyses": db.count_events(user_id, "ai_analysis", since),
            "chat_messages": db.count_events(user_id, "chat_ai", since)}


@dataclass
class AIPlan:
    provider: Optional[LLMProvider]
    notice: Optional[str] = None
    counts_against_quota: bool = False


def own_provider(profile: db.Profile) -> Optional[LLMProvider]:
    raw = decrypt_key(profile.llm_key_enc)
    return user_provider(raw) if raw else None


def plan_analysis(profile: db.Profile, wants_ai: bool) -> AIPlan:
    """Which LLM (if any) an analysis may use: the user's own key, the server key within the daily limit, or none."""
    if not wants_ai:
        return AIPlan(None)
    current = settings()
    mine = own_provider(profile)
    if mine is not None:
        return AIPlan(mine)
    if not current.ai_enabled:
        return AIPlan(None, "AI analysis is paused by the administrator, so this document was checked by the "
                            "built-in rules only. Add your own Groq key in Settings to use AI now.")
    server = get_provider()
    if server is None:
        return AIPlan(None)
    limit = ai_limit_for(profile, current)
    if db.count_events(profile.id, "ai_analysis", db.day_start()) >= limit:
        return AIPlan(None, f"You have used today's {limit} AI analyses, so this document was checked by the built-in "
                            "rules only. The limit resets at midnight UTC, or add your own Groq key in Settings.")
    return AIPlan(server, counts_against_quota=True)


def plan_chat(profile: db.Profile) -> AIPlan:
    current = settings()
    mine = own_provider(profile)
    if mine is not None:
        return AIPlan(mine)
    if not current.ai_enabled:
        return AIPlan(None, "AI answers are paused by the administrator; showing the most relevant passages instead.")
    server = get_provider()
    if server is None:
        return AIPlan(None)
    if db.count_events(profile.id, "chat_ai", db.day_start()) >= current.chat_daily_limit:
        return AIPlan(None, f"You have used today's {current.chat_daily_limit} AI answers; showing the most relevant "
                            "passages instead. Add your own Groq key in Settings for unlimited answers.")
    return AIPlan(server, counts_against_quota=True)
