from collections import Counter
from typing import List, Tuple
from app.lab.schemas import NGramItem
from app.config import FALLBACK_STOP_WORDS

_stop_words = set(FALLBACK_STOP_WORDS)


def extract_ngrams(tokens: List[str], n: int, top_k: int = 10, filter_stops: bool = True) -> List[NGramItem]:
    """
    Extract n-grams (unigrams, bigrams, trigrams) and return the most frequent occurrences.
    """
    if len(tokens) < n or n < 1:
        return []

    ngram_tuples = []
    for i in range(len(tokens) - n + 1):
        window = tokens[i : i + n]
        # For bigrams and trigrams, avoid n-grams that both start and end with stop words
        if filter_stops and n > 1:
            if window[0] in _stop_words and window[-1] in _stop_words:
                continue
            # Must contain at least one meaningful word (length > 2 and not stop word)
            meaningful = [w for w in window if len(w) > 2 and w not in _stop_words]
            if not meaningful:
                continue
        elif filter_stops and n == 1:
            if window[0] in _stop_words or len(window[0]) <= 2:
                continue

        phrase = " ".join(window)
        ngram_tuples.append(phrase)

    counter = Counter(ngram_tuples)
    return [NGramItem(ngram=phrase, frequency=freq) for phrase, freq in counter.most_common(top_k)]


def get_all_ngrams(cleaned_tokens: List[str], raw_tokens: List[str]) -> Tuple[List[NGramItem], List[NGramItem], List[NGramItem]]:
    """
    Returns unigrams from cleaned tokens, and bigrams/trigrams from raw tokens (with smart filtering).
    """
    unigrams = extract_ngrams(cleaned_tokens, n=1, top_k=10, filter_stops=False)
    bigrams = extract_ngrams(raw_tokens, n=2, top_k=10, filter_stops=True)
    trigrams = extract_ngrams(raw_tokens, n=3, top_k=10, filter_stops=True)
    return unigrams, bigrams, trigrams
