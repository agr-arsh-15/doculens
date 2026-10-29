import math
from collections import Counter
from typing import List
from app.lab.schemas import KeywordScore
from app.config import FALLBACK_STOP_WORDS

_stop_words_list = list(FALLBACK_STOP_WORDS)


def compute_tfidf_keywords(sentences: List[str], top_k: int = 15) -> List[KeywordScore]:
    """
    Compute TF-IDF scores across document sentences to extract high-information keywords.
    Uses scikit-learn TfidfVectorizer if available, with mathematical fallback.
    """
    if not sentences:
        return []

    # Attempt scikit-learn TfidfVectorizer
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        clean_stops = [w for w in _stop_words_list if w.isalnum()]
        vectorizer = TfidfVectorizer(
            stop_words=clean_stops,
            ngram_range=(1, 2),
            max_df=0.85,
            min_df=1,
            max_features=100
        )
        tfidf_matrix = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()
        
        # Average tf-idf score across sentences
        mean_scores = tfidf_matrix.mean(axis=0).A1
        keyword_scores = [
            (feature_names[i], float(mean_scores[i])) 
            for i in range(len(feature_names))
            if len(feature_names[i]) > 2
        ]
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Normalize top score to 1.0
        max_score = keyword_scores[0][1] if keyword_scores else 1.0
        return [
            KeywordScore(
                term=term, 
                score=round((score / max_score) * 100.0, 1) if max_score > 0 else 50.0
            ) 
            for term, score in keyword_scores[:top_k]
        ]
    except Exception:
        pass

    # Mathematical fallback TF-IDF calculation
    docs = [s.lower().split() for s in sentences if len(s.strip()) > 3]
    if not docs:
        return []

    num_docs = len(docs)
    df_counter = Counter()
    tf_counter = Counter()

    for doc in docs:
        unique_words = set(w for w in doc if len(w) > 2 and w not in FALLBACK_STOP_WORDS)
        for w in unique_words:
            df_counter[w] += 1
        for w in doc:
            if len(w) > 2 and w not in FALLBACK_STOP_WORDS:
                tf_counter[w] += 1

    scores = []
    total_tokens = sum(tf_counter.values()) or 1
    for word, tf in tf_counter.items():
        df = df_counter[word]
        # Smooth IDF
        idf = math.log((num_docs + 1) / (df + 1)) + 1.0
        normalized_tf = tf / total_tokens
        score = normalized_tf * idf
        scores.append((word, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    max_score = scores[0][1] if scores else 1.0
    return [
        KeywordScore(
            term=term, 
            score=round((score / max_score) * 100.0, 1) if max_score > 0 else 50.0
        )
        for term, score in scores[:top_k]
    ]
