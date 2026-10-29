from typing import List

from fastapi import APIRouter

from app.classify.jurisdiction import JURISDICTION_LABELS
from app.llm.provider import provider_status
from app.models.schemas import HealthOut, Perspective, PlaybookClauseOut, PlaybookOut
from app.nlp.embeddings import embedder
from app.playbooks.citations import source_links
from app.playbooks.loader import CATEGORY_LABELS, load_playbooks

router = APIRouter(prefix="/api", tags=["meta"])

VERSION = "3.0.0"


@router.get("/health", response_model=HealthOut)
def health():
    return HealthOut(status="ok", llm=provider_status(), embeddings=embedder.status(),
                     playbooks=sorted(load_playbooks()), version=VERSION)


@router.get("/playbooks", response_model=List[PlaybookOut])
def playbooks():
    out = []
    for b in load_playbooks().values():
        out.append(PlaybookOut(
            id=b.id, name=b.name, version=b.version, description=b.description,
            perspectives=[Perspective(id=p.id, label=p.label, description=p.description) for p in b.perspectives],
            clauses=[PlaybookClauseOut(id=c.id, label=c.label, category=c.category, importance=c.importance,
                                       description=c.description, market_standard=c.market_standard or None,
                                       sources=source_links(c.sources), references=source_links(c.references))
                     for c in b.clauses],
            red_flag_count=sum(len(c.red_flags) for c in b.clauses) + len(b.hidden_patterns),
        ))
    return out


@router.get("/meta")
def meta():
    return {"jurisdictions": JURISDICTION_LABELS, "categories": CATEGORY_LABELS,
            "doc_types": {b.id: b.name for b in load_playbooks().values()}}
