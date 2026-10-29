import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.analysis.values import sentence_bounds
from app.models.schemas import Clause, Finding
from app.playbooks.loader import Playbook, PerspectiveSpec

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


@dataclass
class AnalysisContext:
    text: str
    clauses: List[Clause]
    playbook: Playbook
    perspective: PerspectiveSpec
    jurisdiction: str
    warnings: List[str] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    @property
    def clause_by_id(self) -> Dict[str, Clause]:
        return {c.id: c for c in self.clauses}

    def clauses_of_type(self, clause_type: str) -> List[Clause]:
        return [c for c in self.clauses if clause_type in c.clause_types]

    def clause_at(self, offset: int) -> Optional[Clause]:
        best = None
        for c in self.clauses:
            if c.start <= offset < c.end and (best is None or c.end - c.start < best.end - best.start):
                best = c
        return best

    def new_id(self) -> str:
        return f"tmp{next(self._ids)}"

    def is_risky_for_user(self, risk_for: List[str]) -> bool:
        return self.perspective.id in risk_for

    def sentence_quote(self, start: int, end: int, max_len: int = 420):
        s, e = sentence_bounds(self.text, start, end)
        if e - s > max_len:
            cut = max(s, start - max_len // 3)
            if cut > s:
                space = self.text.find(" ", cut, start)
                cut = space + 1 if space != -1 else cut
            sentence_end, s = e, cut
            e = min(e, s + max_len)
            if e < sentence_end:
                space = self.text.rfind(" ", end, e)
                e = space if space != -1 else e
        quote = self.text[s:e].strip()
        lead = len(self.text[s:e]) - len(self.text[s:e].lstrip())
        return quote, s + lead, s + lead + len(quote)


def max_severity(a: str, b: str) -> str:
    return a if SEVERITY_ORDER[a] >= SEVERITY_ORDER[b] else b


def finding_sort_key(f: Finding):
    return (-SEVERITY_ORDER[f.severity], f.favorable, -(f.score_impact or 0), f.quote_start or 0)
