import contextlib
import io
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, documents, meta
from app.config import CORS_ORIGINS, DISCLAIMER
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
        if _nltk_has(nltk, resource):
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(analyses.router)
app.include_router(meta.router)


@app.get("/")
def root():
    return {"service": "DocuLens API", "version": meta.VERSION, "docs": "/docs", "disclaimer": DISCLAIMER}
