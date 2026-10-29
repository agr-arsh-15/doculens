from typing import Iterable, List, Optional

from app.models.schemas import SourceLink
from app.playbooks.loader import resolve_sources


def source_links(*id_lists: Iterable[str], jurisdiction: Optional[str] = None) -> List[SourceLink]:
    """Resolve source ids into links without duplicates; sources for the document's jurisdiction come first."""
    ids = [i for ids in id_lists for i in (ids or [])]
    specs = resolve_sources(ids)
    if jurisdiction:
        specs = sorted(specs, key=lambda s: jurisdiction not in s.jurisdictions and "GLOBAL" not in s.jurisdictions)
    return [SourceLink(id=s.id, title=s.title, publisher=s.publisher, url=s.url, tier=s.tier) for s in specs]


def merge_links(a: List[SourceLink], b: List[SourceLink]) -> List[SourceLink]:
    seen, out = set(), []
    for link in a + b:
        key = link.id or link.url or link.title
        if key not in seen:
            seen.add(key)
            out.append(link)
    return out
