import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from app.ingestion.parser import page_for_offset
from app.models.schemas import Clause, PageSpan

_NUM_PATTERNS: Sequence[Tuple[re.Pattern, str]] = (
    (re.compile(r"^(?P<num>(?:ARTICLE|Article|SECTION|Section|CLAUSE|Clause)\s+[0-9IVXivx]+[A-Za-z]?\.?)\s*[:.\-]?\s*"), "article"),
    (re.compile(r"^(?P<num>(?:SCHEDULE|Schedule|ANNEXURE|Annexure|APPENDIX|Appendix|EXHIBIT|Exhibit)\s+[0-9A-Z]{1,3}\b\.?)\s*[:.\-]?\s*"), "schedule"),
    (re.compile(r"^(?P<num>\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+"), "decimal"),
    (re.compile(r"^(?P<num>\d{1,2})[.)]\s+"), "number"),
    (re.compile(r"^(?P<num>\([a-z]{1,2}\)|[a-z]\))\s+"), "alpha"),
    (re.compile(r"^(?P<num>\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))\s+"), "roman"),
    (re.compile(r"^(?P<num>\(\d{1,2}\))\s+"), "paren_number"),
    (re.compile(r"^(?P<num>[A-H])\.\s+(?=[A-Z])"), "letter"),
)

_LEVEL_BY_KIND = {"article": 0, "schedule": 0, "number": 0, "letter": 0, "decimal": 1, "alpha": 2,
                  "paren_number": 2, "roman": 3}

_ADDRESS_OR_SALUTATION = re.compile(r"\bDear\b|\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b|\b\d{6}\b|^\d+\s+[A-Z][a-z]+\s+(?:Drive|Street|St|Road|Rd|Avenue|Ave|Lane|Blvd)\b")
_CLOSING_WORDS = re.compile(r"^(dear|sincerely|regards|yours|best|thank|warm|signed|signature|date|name|title)\b", re.I)


@dataclass
class _Line:
    text: str
    start: int
    end: int


@dataclass
class _Block:
    start: int
    end: int
    number: Optional[str]
    kind: Optional[str]
    heading: Optional[str]
    lines: List[_Line] = field(default_factory=list)


def _lines_with_offsets(text: str) -> List[_Line]:
    lines: List[_Line] = []
    pos = 0
    for raw in text.split("\n"):
        start = pos
        end = pos + len(raw)
        pos = end + 1
        stripped = raw.strip()
        if stripped:
            lead = len(raw) - len(raw.lstrip())
            lines.append(_Line(text=stripped, start=start + lead, end=start + lead + len(stripped)))
    return lines


def _match_number(line: str) -> Tuple[Optional[str], Optional[str], str]:
    for pattern, kind in _NUM_PATTERNS:
        m = pattern.match(line)
        if m:
            return m.group("num").strip(), kind, line[m.end():]
    return None, None, line


def _is_titleish(s: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'&/-]*", s)]
    if not words or len(words) > 12:
        return False
    minor = {"and", "or", "of", "the", "to", "for", "in", "on", "a", "an", "&", "with", "by", "at"}
    major = [w for w in words if w.lower() not in minor]
    if not major:
        return False
    return sum(w[0].isupper() for w in major) / len(major) >= 0.75


def _is_caps(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) > 0.85


def _standalone_heading(line: str, next_line: Optional[_Line]) -> bool:
    s = line.strip()
    if len(s) > 90 or s.endswith((",", ";")) or _CLOSING_WORDS.match(s):
        return False
    if re.search(r"[@$€£₹]|https?://", s) or _ADDRESS_OR_SALUTATION.search(s):
        return False
    if s.endswith(".") and not _is_caps(s):
        return False
    if _is_caps(s):
        return True
    if s.endswith("?") and len(s) <= 80 and next_line is not None and len(next_line.text) >= 60:
        return True
    if not _is_titleish(s.rstrip(":")):
        return False
    if next_line is None:
        return False
    return len(next_line.text) >= 60 or _match_number(next_line.text)[0] is not None


def _split_inline_heading(rest: str, is_whole_line_short: bool) -> Tuple[Optional[str], str]:
    rest = rest.strip()
    if not rest:
        return None, ""
    m = re.match(r"^([A-Z][^.:\n]{1,70}?)\s*(?:[:.]|\s-\s)\s+(?=\S)", rest)
    if m:
        candidate = m.group(1).strip()
        if (_is_titleish(candidate) or _is_caps(candidate)) and len(candidate.split()) <= 9:
            return candidate, rest[m.end():]
    if is_whole_line_short and len(rest) <= 90 and (rest.endswith((":", "?")) or _is_titleish(rest) or _is_caps(rest)):
        return rest.rstrip(":. -").strip() or None, ""
    return None, rest


_RUN_IN = re.compile(r"^([A-Z][\w&/'-]*(?:\s+[\w&/'-]+){0,5})\s*:\s+(?=\S)")


def _run_in_heading(line: str, prev: Optional[_Line]) -> Optional[str]:
    """'Start Date: Your first day...' opening a new paragraph: the label is the clause heading."""
    if len(line) < 40 or (prev is not None and prev.text[-1:] not in ".:;!?)\""):
        return None
    m = _RUN_IN.match(line)
    if not m or not (_is_titleish(m.group(1)) or _is_caps(m.group(1))):
        return None
    return m.group(1).strip()


def _sentence_case_heading(rest: str, next_line: Optional[_Line]) -> bool:
    """'5. Other important information' on its own line, followed by body text."""
    s = rest.strip()
    words = s.split()
    if not words or len(words) > 8 or len(s) > 70 or next_line is None or len(next_line.text) < 40:
        return False
    if not s[0].isupper() or s[-1] in ".,;" or words[-1].lower() in {"and", "or", "the", "of", "to", "that"}:
        return False
    return not re.search(r"[$€£₹%\d]", s)


def _build_blocks(text: str, heading_hints: Sequence[int]) -> List[_Block]:
    lines = _lines_with_offsets(text)
    hint_set = set(heading_hints)
    blocks: List[_Block] = []
    current: Optional[_Block] = None

    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else None
        number, kind, rest = _match_number(line.text)
        is_hint = line.start in hint_set
        if number is not None:
            heading, _ = _split_inline_heading(rest, len(line.text) <= 90 and (next_line is not None))
            if heading is None and kind in ("number", "decimal", "article") and _sentence_case_heading(rest, next_line):
                heading = rest.strip()
            current = _Block(start=line.start, end=line.end, number=number, kind=kind, heading=heading, lines=[line])
            blocks.append(current)
            continue
        if is_hint or _standalone_heading(line.text, next_line):
            current = _Block(start=line.start, end=line.end, number=None, kind="heading",
                             heading=line.text.rstrip(":").strip(), lines=[line])
            blocks.append(current)
            continue
        run_in = _run_in_heading(line.text, lines[i - 1] if i else None)
        if run_in:
            current = _Block(start=line.start, end=line.end, number=None, kind="heading", heading=run_in, lines=[line])
            blocks.append(current)
            continue
        if current is None or current.kind == "preamble_para":
            current = _Block(start=line.start, end=line.end, number=None, kind="paragraph", heading=None, lines=[line])
            blocks.append(current)
            continue
        current.lines.append(line)
        current.end = line.end
    return blocks


def _paragraph_blocks(text: str) -> List[_Block]:
    blocks: List[_Block] = []
    for m in re.finditer(r"[^\n](?:.|\n(?!\n))*", text):
        chunk = m.group(0)
        stripped = chunk.strip()
        if not stripped:
            continue
        lead = len(chunk) - len(chunk.lstrip())
        start = m.start() + lead
        blocks.append(_Block(start=start, end=start + len(stripped), number=None, kind="paragraph", heading=None))
    return blocks


def _split_long(block: _Block, text: str, limit: int = 2400) -> List[_Block]:
    if block.end - block.start <= limit:
        return [block]
    body = text[block.start:block.end]
    pieces: List[_Block] = []
    for m in re.finditer(r"[^\n](?:.|\n(?!\n))*", body):
        stripped = m.group(0).strip()
        if not stripped:
            continue
        start = block.start + m.start() + (len(m.group(0)) - len(m.group(0).lstrip()))
        pieces.append(_Block(start=start, end=start + len(stripped), number=None, kind="paragraph", heading=None))
    if len(pieces) <= 1:
        return [block]
    pieces[0].number, pieces[0].kind, pieces[0].heading = block.number, block.kind, block.heading
    for p in pieces[1:]:
        p.heading = block.heading
    return pieces


def segment_document(text: str, pages: List[PageSpan], heading_hints: Sequence[int] = ()) -> List[Clause]:
    blocks = _build_blocks(text, heading_hints)
    structured = sum(1 for b in blocks if b.number or b.kind == "heading")
    if len(text) > 1500 and structured < 3:
        blocks = _paragraph_blocks(text)

    expanded: List[_Block] = []
    for b in blocks:
        expanded.extend(_split_long(b, text))

    clauses: List[Clause] = []
    stack: List[Clause] = []
    pending_heading: Optional[str] = None
    pending_start: Optional[int] = None
    for idx, b in enumerate(expanded):
        body = text[b.start:b.end].strip()
        if not body:
            continue
        heading_only = b.heading is not None and len(body) <= len(b.heading) + 12 and "\n" not in body
        nxt = expanded[idx + 1] if idx + 1 < len(expanded) else None
        level = _LEVEL_BY_KIND.get(b.kind or "", 0)
        if b.kind in ("heading", "paragraph"):
            level = 0 if b.kind == "heading" else (stack[-1].level + 1 if stack and stack[-1].heading and stack[-1].text.strip() == stack[-1].heading else 0)

        if heading_only and nxt is not None and not b.number and nxt.heading is None:
            pending_heading = b.heading
            pending_start = b.start
            continue

        start = pending_start if pending_start is not None and b.heading is None else b.start
        heading = b.heading if b.heading else pending_heading
        pending_heading, pending_start = None, None

        while stack and stack[-1].level >= level:
            stack.pop()
        clause = Clause(
            id=f"C{len(clauses) + 1}",
            number=b.number,
            heading=heading,
            text=text[start:b.end],
            start=start,
            end=b.end,
            page=page_for_offset(pages, start),
            parent_id=stack[-1].id if stack else None,
            level=level,
        )
        clauses.append(clause)
        stack.append(clause)

    if not clauses and text.strip():
        clauses.append(Clause(id="C1", text=text, start=0, end=len(text), page=1))
    return clauses


def clause_label(clause: Clause) -> str:
    parts = []
    if clause.number:
        parts.append(clause.number)
    if clause.heading:
        parts.append(clause.heading)
    return " ".join(parts) if parts else f"Paragraph {clause.id[1:]}"
