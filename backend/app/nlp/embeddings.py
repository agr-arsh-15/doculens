import logging
import threading
from typing import Dict, List, Optional

import numpy as np

from app.config import DISABLE_NEURAL_EMBEDDINGS, EMBEDDING_MODEL

log = logging.getLogger(__name__)


class Embedder:
    """Sentence similarity with a neural ONNX model when available and a TF-IDF fallback otherwise."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False
        self._error: Optional[str] = None
        self._cache: Dict[str, np.ndarray] = {}

    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if DISABLE_NEURAL_EMBEDDINGS:
                self._error = "disabled by configuration"
            else:
                try:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(model_name=EMBEDDING_MODEL)
                    list(self._model.embed(["warm up"]))
                except Exception as exc:  # network or runtime failures fall back to TF-IDF
                    log.warning("Neural embeddings unavailable, using TF-IDF: %s", exc)
                    self._model = None
                    self._error = str(exc)[:200]
            self._loaded = True

    def warm_up(self) -> None:
        threading.Thread(target=self._load, daemon=True).start()

    @property
    def backend(self) -> str:
        self._load()
        return f"neural:{EMBEDDING_MODEL}" if self._model is not None else "tfidf"

    def status(self) -> Dict[str, Optional[str]]:
        return {
            "backend": ("neural" if self._model is not None else "tfidf") if self._loaded else "loading",
            "model": EMBEDDING_MODEL,
            "error": self._error,
        }

    def _encode(self, texts: List[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            vectors = list(self._model.embed([t[:2000] for t in missing], batch_size=32))
            for text, vec in zip(missing, vectors):
                v = np.asarray(vec, dtype=np.float32)
                self._cache[text] = v / (np.linalg.norm(v) or 1.0)
            if len(self._cache) > 20000:
                self._cache.clear()
        return np.vstack([self._cache[t] for t in texts])

    def similarity(self, a: List[str], b: List[str]) -> np.ndarray:
        """Cosine similarity matrix of shape (len(a), len(b))."""
        if not a or not b:
            return np.zeros((len(a), len(b)), dtype=np.float32)
        self._load()
        if self._model is not None:
            try:
                return self._encode(a) @ self._encode(b).T
            except Exception as exc:
                log.warning("Embedding failed, falling back to TF-IDF: %s", exc)
        return _tfidf_similarity(a, b)


def _tfidf_similarity(a: List[str], b: List[str]) -> np.ndarray:
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    try:
        matrix = vectorizer.fit_transform(a + b)
    except ValueError:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    sims = (matrix[: len(a)] @ matrix[len(a):].T).toarray()
    return sims.astype(np.float32)


embedder = Embedder()
