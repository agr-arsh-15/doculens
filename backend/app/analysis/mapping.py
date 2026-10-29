import re
from typing import List

import numpy as np

from app.analysis.context import AnalysisContext
from app.nlp.embeddings import embedder

ASSIGN_THRESHOLD = 0.42


def _keyword_score(text_lower: str, heading_lower: str, keywords: List[str], label: str) -> float:
    hits = sum(1 for k in keywords if k in text_lower)
    score = min(1.0, hits * 0.3)
    label_words = [w for w in re.findall(r"[a-z]+", label.lower()) if len(w) > 3]
    if heading_lower and (any(k in heading_lower for k in keywords) or any(w in heading_lower for w in label_words)):
        score = min(1.0, score + 0.45)
    return score


def map_clauses(ctx: AnalysisContext) -> None:
    """Assign playbook clause types to each segmented clause using embeddings plus keyword evidence."""
    specs = ctx.playbook.clauses
    if not specs or not ctx.clauses:
        return
    spec_texts = [f"{s.label}. {s.description} {s.prototype}" for s in specs]
    clause_texts = [f"{c.heading or ''}. {c.text[:900]}" for c in ctx.clauses]
    sims = embedder.similarity(clause_texts, spec_texts)
    neural = embedder.backend.startswith("neural")
    if neural:
        emb_norm = np.clip((sims - 0.45) / 0.35, 0.0, 1.0)
    else:
        peak = float(sims.max()) if sims.size else 1.0
        emb_norm = sims / (peak or 1.0)

    for i, clause in enumerate(ctx.clauses):
        text_lower = clause.text.lower()
        heading_lower = (clause.heading or "").lower()
        scores = {}
        for j, spec in enumerate(specs):
            kw = _keyword_score(text_lower, heading_lower, spec.keywords, spec.label)
            score = 0.55 * float(emb_norm[i, j]) + 0.45 * kw
            if kw == 0 and float(emb_norm[i, j]) < 0.8:
                score *= 0.5
            scores[spec.id] = round(score, 3)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        clause.type_scores = dict(ranked[:3])
        if len(clause.text) < 40 and not clause.heading:
            clause.clause_types = []
            continue
        top_score = ranked[0][1]
        clause.clause_types = [cid for cid, s in ranked[:2] if s >= ASSIGN_THRESHOLD and s >= top_score * 0.75]
