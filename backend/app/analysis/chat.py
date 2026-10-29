"""Ask-the-document: retrieval over this document's clauses, answered by the LLM with clause citations."""
import logging
import re
from typing import List

import numpy as np

from app.llm.provider import LLMError, get_provider
from app.llm.redact import Redactor
from app.models.schemas import AnalysisResult, ChatMessage, ChatResponse, Citation, Clause
from app.nlp.embeddings import embedder
from app.structure.segmenter import clause_label

log = logging.getLogger(__name__)

_STOP = {"the", "a", "an", "is", "are", "what", "which", "who", "how", "does", "do", "can", "i", "my", "me", "of", "to",
         "in", "on", "for", "and", "or", "if", "this", "that", "it", "be", "there", "any", "about", "with", "will", "they"}

_SYSTEM = """You answer questions about ONE document using only the numbered clauses provided.
Rules:
- Cite every claim with the clause id in square brackets, e.g. [C4]. Only cite ids that appear in the context.
- If the clauses do not answer the question, say plainly that the document does not address it, and say what is related.
- Be concise (at most 6 sentences or a short list). Plain English, no legalese.
- Do not invent facts, numbers or clauses. This is not legal advice; do not claim certainty about enforceability."""


def _tokens(text: str) -> set:
    """Crude stems (strip plural, cap at 6 chars) so 'resign' matches 'resignation' and 'year' matches 'years'."""
    return {t.rstrip("s")[:6] for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP and len(t) > 2}


def retrieve(result: AnalysisResult, question: str, k: int = 5) -> List[Clause]:
    clauses = [c for c in result.clauses if len(c.text.strip()) > 20]
    if not clauses:
        return []
    docs = [f"{clause_label(c)}. {c.text[:1500]}" for c in clauses]
    sims = embedder.similarity([question], docs)[0]
    q = _tokens(question)
    kw = np.array([len(q & _tokens(d)) / max(1, len(q)) for d in docs], dtype=np.float32)
    span = float(sims.max() - sims.min()) or 1.0
    score = 0.6 * (sims - sims.min()) / span + 0.4 * kw
    order = np.argsort(-score)[:k]
    return [clauses[i] for i in order if score[i] > 0.05]


def _body(c: Clause) -> str:
    first, _, rest = c.text.partition("\n")
    return rest if rest.strip() and c.heading and c.heading.lower() in first.lower() else c.text


def _excerpt(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def answer_question(result: AnalysisResult, question: str, history: List[ChatMessage]) -> ChatResponse:
    hits = retrieve(result, question)
    by_id = {c.id: c for c in result.clauses}
    related = [f for f in result.findings if set(f.clause_ids) & {c.id for c in hits} and not f.favorable]
    provider = get_provider()

    if provider is not None and hits:
        redactor = Redactor(names=[p.name.split(' ("')[0] for p in result.parties])
        context = "\n\n".join(f"[{c.id}] {clause_label(c)}\n{redactor.redact(c.text[:1800])}" for c in hits)
        notes = "\n".join(f"- [{f.clause_ids[0]}] {f.severity}: {f.title}" for f in related[:6])
        messages = [{"role": "system", "content": _SYSTEM}]
        for m in history[-6:]:
            messages.append({"role": m.role, "content": redactor.redact(m.content[:1500])})
        messages.append({"role": "user", "content": (
            f"Document: {result.doc_type_label}. Reader: {result.perspective_label}.\n\nClauses:\n{context}\n\n"
            + (f"Risk findings already identified:\n{notes}\n\n" if notes else "")
            + f"Question: {redactor.redact(question)}"
        )})
        try:
            answer = redactor.restore(provider.chat_text(messages, max_tokens=700))
            cited = [cid for cid in dict.fromkeys(re.findall(r"\[(C\d+)\]", answer)) if cid in by_id]
            if not cited:
                cited = [c.id for c in hits[:2]]
            citations = [Citation(clause_id=cid, label=clause_label(by_id[cid]), excerpt=_excerpt(_body(by_id[cid]))) for cid in cited]
            return ChatResponse(answer=answer.strip(), citations=citations, mode="llm")
        except LLMError as exc:
            log.warning("Chat LLM call failed: %s", exc)

    if not hits:
        return ChatResponse(answer="I could not find anything in this document related to that question.", citations=[], mode="retrieval")
    lines = ["AI answers need an LLM key, so here are the passages of this document most relevant to your question:"]
    for c in hits[:3]:
        lines.append(f"- [{c.id}] {clause_label(c)}: {_excerpt(_body(c), 260)}")
    if related:
        lines.append("Related findings: " + "; ".join(f"{f.title} [{f.clause_ids[0]}]" for f in related[:3]) + ".")
    citations = [Citation(clause_id=c.id, label=clause_label(c), excerpt=_excerpt(_body(c))) for c in hits[:3]]
    return ChatResponse(answer="\n".join(lines), citations=citations, mode="retrieval")
