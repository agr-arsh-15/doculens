import contextlib
import io
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, analyses, documents, me, meta
from app.config import AUTH_MODE, CORS_ORIGINS, DISCLAIMER, IS_PRODUCTION, LAB_USE_WORDNET
from app.security import SecurityHeadersMiddleware, limiter
from app.nlp.embeddings import embedder
from app.playbooks.loader import load_playbooks
from app.storage import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_NLTK_PACKAGES = {
    "punkt_tab": "tokenizers/punkt_tab",
    "stopwords": "corpora/stopwords",
    "wordnet": "corpora/wordnet",
    "averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
}


def _nltk_has(nltk, resource: str) -> bool:
    for candidate in (resource, f"{resource}.zip"):
        try:
            nltk.data.find(candidate)
            return True
        except LookupError:
            continue
    return False


def _ensure_nltk_data() -> None:
    """Best-effort download for the NLP Lab; every lab step has a regex fallback if this fails."""
    try:
        import nltk
    except ImportError:
        return
    log = logging.getLogger(__name__)
    for pkg, resource in _NLTK_PACKAGES.items():
        if _nltk_has(nltk, resource) or (pkg == "wordnet" and not LAB_USE_WORDNET):
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                ok = nltk.download(pkg, quiet=True, raise_on_error=False)
            if not ok:
                log.info("NLTK resource %s unavailable; the NLP Lab will use its regex fallback.", pkg)
        except Exception as exc:
            log.info("NLTK download of %s skipped: %s", pkg, exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    db.mark_interrupted()
    load_playbooks()
    embedder.warm_up()
    threading.Thread(target=_ensure_nltk_data, daemon=True).start()
    yield


app = FastAPI(
    title="DocuLens API",
    description="Risk analysis for contracts, offer letters, terms of service and compliance documents. " + DISCLAIMER,
    version=meta.VERSION,
    lifespan=lifespan,
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limited(request: Request, exc: RateLimitExceeded):
    return JSONResponse({"detail": "Too many requests. Please wait a minute and try again."}, status_code=429)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.include_router(documents.router)
app.include_router(analyses.router)
app.include_router(me.router)
app.include_router(admin.router)
app.include_router(meta.router)


@app.get("/")
def root():
    return {"service": "DocuLens API", "version": meta.VERSION, "auth": AUTH_MODE, "disclaimer": DISCLAIMER}
