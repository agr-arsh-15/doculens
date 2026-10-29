import re
from functools import lru_cache
from typing import Dict, List, Tuple

from app.config import LAB_USE_WORDNET
from app.lab.schemas import LemmaSample


@lru_cache(maxsize=1)
def _nltk_tools():
    """Return (lemmatizer, pos_tag) when the WordNet and perceptron-tagger data are usable."""
    lemmatizer = tagger = None
    try:
        if not LAB_USE_WORDNET:
            raise LookupError("WordNet disabled by configuration")
        from nltk.stem import WordNetLemmatizer
        candidate = WordNetLemmatizer()
        candidate.lemmatize("contracts")
        lemmatizer = candidate
    except Exception:
        pass
    try:
        from nltk import pos_tag
        pos_tag(["probe"])
        tagger = pos_tag
    except Exception:
        pass
    return lemmatizer, tagger


def _get_wordnet_pos(treebank_tag: str):
    """Map POS tag to first character lemmatize() accepts."""
    if treebank_tag.startswith('J'):
        return 'a'  # ADJ
    elif treebank_tag.startswith('V'):
        return 'v'  # VERB
    elif treebank_tag.startswith('N'):
        return 'n'  # NOUN
    elif treebank_tag.startswith('R'):
        return 'r'  # ADV
    else:
        return 'n'


def _fallback_lemmatize(word: str) -> str:
    """Lightweight rule-based suffix normalization fallback."""
    w = word.lower()
    # Common plural & inflection rules
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('es') and len(w) > 3 and (w.endswith('sses') or w.endswith('shes') or w.endswith('ches')):
        return w[:-2]
    if w.endswith('s') and not w.endswith('ss') and len(w) > 3:
        return w[:-1]
    if w.endswith('ing') and len(w) > 4:
        return w[:-3]
    if w.endswith('ed') and len(w) > 3:
        return w[:-2] if not w.endswith('eed') else w
    if w.endswith('tion') or w.endswith('tions'):
        return re.sub(r'tions?$', 'tion', w)
    return w


def lemmatizer_name() -> str:
    return "WordNet" if _nltk_tools()[0] else "rule-based suffixes"


def tag_pos_and_lemmatize(tokens: List[str]) -> Tuple[Dict[str, int], List[LemmaSample]]:
    """
    Performs POS tagging and lemmatization on tokens.
    Returns:
        pos_distribution: {"Nouns": count, "Verbs": count, "Adjectives": count, "Adverbs": count, "Other": count}
        sample_lemmas: list of 10-15 prominent LemmaSample instances showcasing inflection reduction
    """
    if not tokens:
        return {"Nouns": 0, "Verbs": 0, "Adjectives": 0, "Adverbs": 0, "Other": 0}, []

    _lemmatizer, _pos_tagger = _nltk_tools()
    pos_counts = {"Nouns": 0, "Verbs": 0, "Adjectives": 0, "Adverbs": 0, "Other": 0}
    sample_lemmas: List[LemmaSample] = []
    seen_samples = set()

    # POS tagging
    tagged_tokens = []
    if _pos_tagger:
        try:
            tagged_tokens = _pos_tagger(tokens)
        except Exception:
            pass

    if not tagged_tokens:
        # Heuristic tagging
        for t in tokens:
            if t.endswith(('ing', 'ed', 'ize', 'fy')):
                tagged_tokens.append((t, 'VB'))
            elif t.endswith(('able', 'ible', 'ive', 'al', 'ous', 'ful')):
                tagged_tokens.append((t, 'JJ'))
            elif t.endswith('ly'):
                tagged_tokens.append((t, 'RB'))
            else:
                tagged_tokens.append((t, 'NN'))

    for word, tag in tagged_tokens:
        # Update POS distribution
        if tag.startswith('N'):
            pos_counts["Nouns"] += 1
            pos_category = "Noun"
        elif tag.startswith('V'):
            pos_counts["Verbs"] += 1
            pos_category = "Verb"
        elif tag.startswith('J'):
            pos_counts["Adjectives"] += 1
            pos_category = "Adjective"
        elif tag.startswith('R'):
            pos_counts["Adverbs"] += 1
            pos_category = "Adverb"
        else:
            pos_counts["Other"] += 1
            pos_category = "Other"

        # Lemmatize
        if _lemmatizer:
            try:
                wn_pos = _get_wordnet_pos(tag)
                lemma = _lemmatizer.lemmatize(word, pos=wn_pos)
            except Exception:
                lemma = _fallback_lemmatize(word)
        else:
            lemma = _fallback_lemmatize(word)

        # Collect distinct interesting transformations
        if word != lemma and word not in seen_samples and len(sample_lemmas) < 15:
            seen_samples.add(word)
            sample_lemmas.append(LemmaSample(word=word, lemma=lemma, pos=pos_category))

    # If few samples had inflections, fill up to 8 samples with common terms
    if len(sample_lemmas) < 6:
        for word, tag in tagged_tokens[:30]:
            if word not in seen_samples and len(sample_lemmas) < 10:
                seen_samples.add(word)
                sample_lemmas.append(LemmaSample(
                    word=word, 
                    lemma=_fallback_lemmatize(word), 
                    pos="Noun" if tag.startswith('N') else "Verb" if tag.startswith('V') else "Modifier"
                ))

    return pos_counts, sample_lemmas
