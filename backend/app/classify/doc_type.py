import re
from typing import List, Tuple

from app.models.schemas import DocTypeCandidate
from app.nlp.embeddings import embedder
from app.playbooks.loader import load_playbooks


def _keyword_coverage(text_lower: str, keywords: List[str]) -> bool:
    return any(k in text_lower for k in keywords)


def detect_doc_type(text: str) -> Tuple[str, float, List[DocTypeCandidate]]:
    books = load_playbooks()
    head = text[:3000]
    head_lower = head[:800].lower()
    text_lower = text.lower()

    ids = [b for b in books if b != "generic_contract"]
    prototypes: List[str] = []
    owners: List[str] = []
    for book_id in ids:
        for proto in books[book_id].detection.prototypes:
            prototypes.append(proto)
            owners.append(book_id)
    sims = embedder.similarity([head], prototypes)[0] if prototypes else []
    emb = {book_id: 0.0 for book_id in ids}
    for owner, sim in zip(owners, sims):
        emb[owner] = max(emb[owner], float(sim))
    max_emb = max(emb.values()) or 1.0

    scored: List[Tuple[str, float]] = []
    for book_id in ids:
        book = books[book_id]
        title_hits = sum(1 for k in book.detection.title_keywords if re.search(rf"\b{re.escape(k)}\b", head_lower))
        body_hits = sum(1 for k in book.detection.title_keywords if k in text_lower)
        title_score = min(1.0, title_hits * 0.7 + min(body_hits, 3) * 0.1)
        coverage = sum(1 for c in book.clauses if _keyword_coverage(text_lower, c.keywords)) / max(1, len(book.clauses))
        score = 0.45 * title_score + 0.35 * (emb[book_id] / max_emb) + 0.20 * coverage
        scored.append((book_id, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    generic_score = 0.38
    candidates = [DocTypeCandidate(id=i, label=books[i].name, score=round(s, 3)) for i, s in scored[:4]]
    best_id, best_score = scored[0]
    if best_score < generic_score:
        best_id, best_score = "generic_contract", generic_score
        candidates.insert(0, DocTypeCandidate(id="generic_contract", label=books["generic_contract"].name,
                                              score=round(generic_score, 3)))
    runner_up = scored[1][1] if len(scored) > 1 else 0.0
    margin = max(0.0, best_score - runner_up)
    confidence = round(min(0.97, 0.35 + best_score * 0.4 + margin * 0.4), 2)
    return best_id, confidence, candidates
