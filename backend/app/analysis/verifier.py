import re
from typing import Optional, Tuple

from rapidfuzz import fuzz

MATCH_THRESHOLD = 88.0


def _norm(s: str) -> str:
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


_CHAR_CLASSES = {
    **{c: "[-\u2010-\u2015]" for c in "-\u2010\u2011\u2012\u2013\u2014\u2015"},
    **{c: "[\"\u201c\u201d]" for c in "\"\u201c\u201d"},
    **{c: "['\u2018\u2019]" for c in "'\u2018\u2019"},
}
_ELLIPSIS = re.compile(r"\.\.\.|…")
MAX_ELLIPSIS_SPAN = 700


def _token_pattern(tok: str) -> str:
    return "".join(_CHAR_CLASSES.get(c, re.escape(c)) for c in tok)


def _exact(haystack: str, needle: str, pos: int = 0) -> Optional[Tuple[int, int]]:
    idx = haystack.lower().find(needle.lower(), pos)
    if idx != -1:
        return idx, idx + len(needle)
    pattern = r"\s+".join(_token_pattern(tok) for tok in needle.split())
    if not pattern:
        return None
    m = re.compile(pattern, re.I).search(haystack, pos)
    return (m.start(), m.end()) if m else None


def _locate_fragments(quote: str, haystack: str) -> Optional[Tuple[int, int]]:
    """An abridged quote ("A ... B ... C") is verified when every fragment appears, in order, within a short span."""
    fragments = [f.strip(" ,;:") for f in _ELLIPSIS.split(quote)]
    fragments = [f for f in fragments if len(f) >= 4]
    if not fragments or sum(len(f) for f in fragments) < 25 or max(len(f) for f in fragments) < 12:
        return None
    first = _exact(haystack, fragments[0])
    while first:
        pos, end = first[1], first[1]
        for frag in fragments[1:]:
            hit = _exact(haystack, frag, pos)
            if hit is None or hit[0] - first[0] > MAX_ELLIPSIS_SPAN:
                break
            pos = end = hit[1]
        else:
            return first[0], end
        first = _exact(haystack, fragments[0], first[0] + 1)
    return None


def locate_quote(quote: str, haystack: str, offset: int = 0) -> Optional[Tuple[int, int, float]]:
    """Find quote inside haystack. Returns absolute (start, end, score) or None if not verifiable."""
    quote = (quote or "").strip().strip('"').strip()
    if len(quote) < 8 or not haystack:
        return None
    quote = re.sub(r"^\s*(\.\.\.|…)\s*|\s*(\.\.\.|…)\s*$", "", quote)
    hit = _exact(haystack, quote)
    if hit:
        return offset + hit[0], offset + hit[1], 100.0
    if _ELLIPSIS.search(quote):
        hit = _locate_fragments(quote, haystack)
        if hit:
            return offset + hit[0], offset + hit[1], 95.0
        head = _ELLIPSIS.split(quote)[0].strip()
        hit = _exact(haystack, head) if len(head) >= 20 else None
        if hit:
            return offset + hit[0], offset + hit[1], 90.0
    if len(_norm(quote)) > len(_norm(haystack)) * 1.2:
        return None
    alignment = fuzz.partial_ratio_alignment(_norm(quote), haystack.lower(), score_cutoff=MATCH_THRESHOLD)
    if alignment is None:
        return None
    start, end = alignment.dest_start, alignment.dest_end
    while start > 0 and haystack[start - 1].isalnum():
        start -= 1
    while end < len(haystack) and haystack[end - 1].isalnum() and haystack[end].isalnum():
        end += 1
    return offset + start, offset + end, float(alignment.score)


def verify_in_clause_or_document(quote: str, clause_text: str, clause_start: int, document: str):
    found = locate_quote(quote, clause_text, clause_start)
    if found is None:
        found = locate_quote(quote, document, 0)
    return found
