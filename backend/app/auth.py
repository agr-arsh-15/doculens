"""Who is calling: verifies the bearer token and returns the caller's profile.

AUTH_MODE=supabase  Supabase access tokens, verified with the project's JWKS (or the legacy HS256 secret).
AUTH_MODE=local     Everyone is the single local admin (laptop installs without accounts).
AUTH_MODE=test      "test-<email>" tokens, for the automated test suites only (refused in production).
"""
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import text

from app import config
from app.storage import db

log = logging.getLogger(__name__)

LOCAL_USER_ID = "local-user"
_TEST_TOKEN = re.compile(r"^test-([^@\s]+@[^@\s]+\.[^@\s]+)$")


@dataclass
class CurrentUser:
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    role: str
    status: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _unauthorized(detail: str = "Sign in to continue.") -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{config.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)


def _decode_supabase(token: str) -> dict:
    options = {"require": ["exp", "sub", "aud"]}
    issuer = f"{config.SUPABASE_URL}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            if not config.SUPABASE_JWT_SECRET:
                raise _unauthorized("This sign-in token type is not accepted.")
            return jwt.decode(token, config.SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated",
                              issuer=issuer, options=options)
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience="authenticated", issuer=issuer,
                          options=options)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Your session has expired. Sign in again.") from exc
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        log.info("Rejected token: %s", type(exc).__name__)
        raise _unauthorized("Invalid sign-in token.") from exc


def _identity(token: Optional[str]) -> dict:
    if config.AUTH_MODE == "local":
        return {"sub": LOCAL_USER_ID, "email": config.LOCAL_USER_EMAIL, "name": "Local user", "role": "admin"}
    if not token:
        raise _unauthorized()
    if config.AUTH_MODE == "test":
        m = _TEST_TOKEN.match(token)
        if not m:
            raise _unauthorized("Invalid sign-in token.")
        email = m.group(1).lower()
        return {"sub": "test-" + re.sub(r"[^a-z0-9]", "-", email), "email": email, "name": email.split("@")[0]}
    if config.AUTH_MODE == "supabase":
        claims = _decode_supabase(token)
        meta = claims.get("user_metadata") or {}
        if not claims.get("email"):
            raise _unauthorized("Your account has no email address.")
        return {"sub": claims["sub"], "email": claims["email"].lower(),
                "name": meta.get("full_name") or meta.get("name"),
                "avatar_url": meta.get("avatar_url") or meta.get("picture")}
    raise HTTPException(500, "Server authentication is misconfigured.")


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def current_user(request: Request) -> CurrentUser:
    ident = _identity(_bearer(request))
    role = "admin" if ident.get("role") == "admin" or ident["email"] in config.ADMIN_EMAILS else "user"
    profile = db.upsert_profile(ident["sub"], ident["email"], ident.get("name"), ident.get("avatar_url"), role)
    if profile.status == "blocked":
        raise HTTPException(403, "Your account has been suspended. Contact the administrator.")
    request.state.user_id = profile.id
    return CurrentUser(id=profile.id, email=profile.email, name=profile.name, avatar_url=profile.avatar_url,
                       role=profile.role, status=profile.status)


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required.")
    return user


def delete_auth_user(user_id: str) -> None:
    """Remove the account from Supabase Auth (no-op outside Supabase mode).

    Uses the Auth Admin API and falls back to deleting the auth.users row over the database connection,
    which the API's database role is allowed to do on Supabase.
    """
    if config.AUTH_MODE != "supabase":
        return
    if config.SUPABASE_SERVICE_ROLE_KEY:
        try:
            r = httpx.delete(f"{config.SUPABASE_URL}/auth/v1/admin/users/{user_id}", timeout=30,
                             headers=config.supabase_service_headers())
            if r.status_code in (200, 204, 404):
                return
            log.warning("Auth Admin delete returned HTTP %s; trying the database", r.status_code)
        except httpx.HTTPError as exc:
            log.warning("Auth Admin delete failed (%s); trying the database", type(exc).__name__)
    if db.engine.dialect.name != "postgresql":
        raise HTTPException(500, "Account deletion is not configured.")
    try:
        with db.engine.begin() as conn:
            conn.execute(text("DELETE FROM auth.users WHERE id = CAST(:id AS uuid)"), {"id": user_id})
    except Exception as exc:
        log.error("Could not delete the auth user: %s", type(exc).__name__)
        raise HTTPException(502, "Could not delete the sign-in account. Try again later.") from exc
