import math
import re
from typing import List, Tuple
from app.config import FALLBACK_STOP_WORDS

_stop_words = set(FALLBACK_STOP_WORDS)


def _sentence_similarity(s1: str, s2: str) -> float:
    """Computes Jaccard/overlap similarity between two sentences."""
    words1 = set(w.lower() for w in re.findall(r'\b[a-zA-Z-]+\b', s1) if w.lower() not in _stop_words and len(w) > 2)
    words2 = set(w.lower() for w in re.findall(r'\b[a-zA-Z-]+\b', s2) if w.lower() not in _stop_words and len(w) > 2)

    if not words1 or not words2:
        return 0.0

    intersection = len(words1.intersection(words2))
    norm = math.log(len(words1) + 1) + math.log(len(words2) + 1)
    return intersection / norm if norm > 0 else 0.0


def extract_textrank_summary(sentences: List[str], top_k: int = 4) -> List[str]:
    """
    Graph-based TextRank summarization algorithm.
    Builds a fully connected graph of sentences, runs PageRank iterations,
    and returns top ranked sentences in chronological order.
    """
    valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    n = len(valid_sentences)

    if n <= top_k:
        return valid_sentences

    # 1. Build Similarity Matrix (Adjacency Graph)
    similarity_matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            sim = _sentence_similarity(valid_sentences[i], valid_sentences[j])
            similarity_matrix[i][j] = sim
            similarity_matrix[j][i] = sim

    # 2. Run PageRank iterations
    d = 0.85  # Damping factor
    scores = [1.0 / n] * n

    for _ in range(25):  # 25 power iterations
        new_scores = [0.0] * n
        for i in range(n):
            sum_in = 0.0
            for j in range(n):
                if i != j:
                    sum_out = sum(similarity_matrix[j])
                    if sum_out > 0:
                        sum_in += (similarity_matrix[j][i] / sum_out) * scores[j]
            new_scores[i] = (1 - d) / n + d * sum_in
        scores = new_scores

    # 3. Select top ranked indices and preserve document sequence
    ranked_indices = sorted(range(n), key=lambda idx: scores[idx], reverse=True)[:top_k]
    chronological_indices = sorted(ranked_indices)

    return [valid_sentences[i] for i in chronological_indices]


def generate_extractive_synthesis(sentences: List[str], domain: str = "legal") -> Tuple[List[str], List[str], List[str]]:
    """
    Extracts key obligations, potential red flags, and recommended amendments
    based on linguistic markers and modal verbs (shall, must, will, agree).
    """
    obligations = []
    red_flags = []
    amendments = []

    for s in sentences:
        s_clean = s.strip()
        s_lower = s_clean.lower()

        # Obligations: mandatory action indicators
        if any(marker in s_lower for marker in ["shall maintain", "shall pay", "shall provide", "agrees to deliver", "must notify", "responsible for"]):
            if len(obligations) < 4 and len(s_clean) < 220:
                obligations.append(s_clean)

        # Red flags: harsh restriction or risk markers
        if any(marker in s_lower for marker in ["immediate termination", "sole discretion", "unilateral", "liquidated damages", "waive any right", "in no event shall"]):
            if len(red_flags) < 4 and len(s_clean) < 220:
                red_flags.append(s_clean)

    # Fallbacks if few matches
    if not obligations and sentences:
        for s in sentences[:3]:
            if any(w in s.lower() for w in ["shall", "agree", "will"]):
                obligations.append(s[:200])

    if not red_flags and sentences:
        for s in sentences:
            if any(w in s.lower() for w in ["liability", "disclaim", "terminate", "forfeit"]):
                red_flags.append(s[:200])
                if len(red_flags) >= 2:
                    break

    # Standard recommendations
    amendments.append("Insert a reciprocal 30-day notice and cure period prior to exercising termination rights.")
    amendments.append("Ensure mutual limitation of liability capped at 12 months fees paid or agreed monetary limit.")
    if domain == "hr":
        amendments.append("Limit non-compete covenants to active direct competitors within 15 miles for a maximum 6-month period.")
    elif domain == "tos":
        amendments.append("Provide a 30-day written email opt-out provision for binding arbitration and unilateral changes.")
    else:
        amendments.append("Establish bilateral indemnification protections for third-party intellectual property claims.")

    return obligations, red_flags, amendments
