import re
from typing import List, Set, Tuple
from app.config import FALLBACK_STOP_WORDS

_stop_words_set: Set[str] = set(FALLBACK_STOP_WORDS)

try:
    import nltk
    try:
        from nltk.corpus import stopwords
        _stop_words_set.update(stopwords.words('english'))
    except Exception:
        pass
except Exception:
    pass


def clean_and_filter_tokens(tokens: List[str]) -> Tuple[List[str], int, float, int]:
    """
    Remove stop words and non-alphanumeric noise from tokens.
    Returns:
        (cleaned_tokens, stop_words_removed_count, reduction_percent, vocabulary_size)
    """
    if not tokens:
        return [], 0, 0.0, 0

    cleaned = []
    removed_count = 0

    for token in tokens:
        t = token.lower().strip()
        # Filter if purely numeric or punctuation or in stop words or length <= 1
        if len(t) <= 1 or t in _stop_words_set or re.match(r'^\d+$', t):
            removed_count += 1
        else:
            cleaned.append(t)

    total = len(tokens)
    reduction_percent = round((removed_count / total * 100.0), 2) if total > 0 else 0.0
    vocabulary_size = len(set(cleaned))

    return cleaned, removed_count, reduction_percent, vocabulary_size
