"""Rate limiting, upload content checks and HTTP security headers."""
from pathlib import Path

from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app import config

_ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md", ".text", ""}


def _rate_key(request: Request) -> str:
    """Per signed-in user where known, otherwise per client IP (proxy headers are trusted by uvicorn)."""
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_key, default_limits=[config.RATE_LIMIT_DEFAULT],
                  enabled=config.AUTH_MODE != "test" or config.IS_PRODUCTION)


def sniff_upload(data: bytes, filename: str) -> None:
    """Reject files whose bytes do not match the claimed type, before any parser touches them."""
    ext = Path(filename).suffix.lower()
    if ext == ".doc":
        raise HTTPException(415, "Legacy .doc files are not supported. Save the file as .docx or PDF and retry.")
    if ext not in _ALLOWED_EXT:
        raise HTTPException(415, "Upload a PDF, DOCX or plain-text file.")
    head = data[:1024]
    if ext == ".pdf" and b"%PDF-" not in head:
        raise HTTPException(415, "This file is not a valid PDF.")
    if ext == ".docx" and not data.startswith(b"PK\x03\x04"):
        raise HTTPException(415, "This file is not a valid DOCX document.")
    if ext in (".txt", ".md", ".text", "") and not head.startswith(b"%PDF-") and b"\x00" in data[:8192]:
        raise HTTPException(415, "Unsupported binary file. Upload a PDF, DOCX or plain-text file.")


_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in _HEADERS.items():
            response.headers.setdefault(k, v)
        if config.IS_PRODUCTION:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
