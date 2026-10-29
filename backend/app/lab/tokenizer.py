import re
from functools import lru_cache
from typing import List


@lru_cache(maxsize=1)
def _nltk_tokenizers():
    """Return (sent_tokenize, word_tokenize) if NLTK punkt_tab is usable, else (None, None)."""
    try:
        from nltk.tokenize import sent_tokenize, word_tokenize
        sent_tokenize("Probe sentence one. Probe two.")
        word_tokenize("probe")
        return sent_tokenize, word_tokenize
    except Exception:
        return None, None


def sentence_tokenizer_name() -> str:
    return "nltk-punkt" if _nltk_tokenizers()[0] else "regex"


_ABBREVIATION_TAIL = re.compile(
    r"\b(?:rs|inr|no|nos|ltd|pvt|inc|co|corp|sec|s|ss|art|para|cl|vs|v|mr|mrs|ms|dr|st|e\.g|i\.e|etc|approx)\.$",
    re.IGNORECASE,
)
_NUMBERING_ONLY = re.compile(r"^(?:\d+(?:\.\d+)*\.?|\(?[a-z]\)|[ivx]+\.)$", re.IGNORECASE)


def _blocks(text: str) -> List[str]:
    """Split on line structure: headings and short unterminated lines become their own block."""
    blocks: List[str] = []
    buf: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            continue
        is_heading = len(line) < 80 and not re.search(r"[.;:,]$", line)
        if is_heading:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            blocks.append(line)
        else:
            buf.append(line)
    if buf:
        blocks.append(" ".join(buf))
    return blocks


def _merge_abbreviation_splits(sentences: List[str]) -> List[str]:
    merged: List[str] = []
    for s in sentences:
        if merged and (_ABBREVIATION_TAIL.search(merged[-1]) or _NUMBERING_ONLY.match(merged[-1])):
            merged[-1] = f"{merged[-1]} {s}"
        else:
            merged.append(s)
    return merged


def segment_sentences(text: str) -> List[str]:
    """Segment document text into individual sentences with legal/abbreviation preservation."""
    if not text.strip():
        return []

    _nltk_sent_tokenizer, _ = _nltk_tokenizers()
    if _nltk_sent_tokenizer:
        try:
            sentences = [s for block in _blocks(text) for s in _nltk_sent_tokenizer(block)]
            merged = _merge_abbreviation_splits([s.strip() for s in sentences if s.strip()])
            cleaned = [s for s in merged if len(s) > 3]
            if cleaned:
                return cleaned
        except Exception:
            pass

    raw = [
        s.strip()
        for block in _blocks(text)
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(])', block)
        if s.strip()
    ]
    results = [s for s in _merge_abbreviation_splits(raw) if len(s) > 3]
    return results or [text.strip()]


def tokenize_words(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words."""
    if not text.strip():
        return []

    _, _nltk_word_tokenizer = _nltk_tokenizers()
    if _nltk_word_tokenizer:
        try:
            tokens = _nltk_word_tokenizer(text)
            return [t.lower() for t in tokens if re.search(r'[a-zA-Z0-9]', t)]
        except Exception:
            pass

    # Regex tokenization
    return [match.group(0).lower() for match in re.finditer(r'\b[a-zA-Z0-9_/-]+\b', text)]
