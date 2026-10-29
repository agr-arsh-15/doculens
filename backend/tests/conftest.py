"""Test environment: isolated data directory, no LLM, deterministic TF-IDF embeddings.

Set DOCULENS_TEST_NEURAL=1 to run the suite with the neural embedding model instead.
These variables must be set before any `app` module is imported, because app.config reads them once.
"""
import os
import tempfile

os.environ["DOCULENS_DATA_DIR"] = tempfile.mkdtemp(prefix="doculens-test-")
os.environ["LLM_PROVIDER"] = "none"
os.environ["AUTH_MODE"] = "test"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["STORAGE_BACKEND"] = "local"
for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
    os.environ[key] = ""
if os.environ.get("DOCULENS_TEST_NEURAL") != "1":
    os.environ["DISABLE_NEURAL_EMBEDDINGS"] = "1"

import pytest  # noqa: E402

from app.analysis.context import AnalysisContext  # noqa: E402
from app.models.schemas import PageSpan  # noqa: E402
from app.playbooks.loader import get_playbook  # noqa: E402
from app.structure.segmenter import segment_document  # noqa: E402


def make_context(text: str, doc_type: str, perspective: str = None, jurisdiction: str = "US") -> AnalysisContext:
    from app.analysis.mapping import map_clauses

    playbook = get_playbook(doc_type)
    clauses = segment_document(text, [PageSpan(page=1, start=0, end=len(text))])
    ctx = AnalysisContext(text=text, clauses=clauses, playbook=playbook, perspective=playbook.perspective(perspective),
                          jurisdiction=jurisdiction)
    map_clauses(ctx)
    return ctx


@pytest.fixture
def context_factory():
    return make_context
