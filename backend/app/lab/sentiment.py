import math
import re
from typing import List
from app.lab.schemas import SentimentMetrics

# Domain-adapted sentiment lexicon for contractual and compliance language
LEGAL_POLARITY_LEXICON = {
    # Protective / Favorable (+ polarity)
    "remedy": 1.5, "protect": 1.8, "entitled": 1.6, "benefit": 1.7, "reasonable": 1.4,
    "mutual": 1.9, "agree": 1.3, "good faith": 2.0, "cure": 1.5, "severability": 1.2,
    "bonus": 2.2, "compensation": 1.6, "insurance": 1.4, "safeguard": 1.8, "consent": 1.3,
    "warrant": 1.2, "vesting": 1.5, "allowance": 1.4, "reimburse": 1.4, "compliant": 1.7,

    # Punitive / Restrictive / Risk (- polarity)
    "breach": -2.5, "default": -2.2, "terminate": -2.0, "penalty": -2.6, "liquidated damages": -2.8,
    "indemnify": -2.4, "indemnification": -2.4, "liability": -1.8, "injunction": -2.1,
    "injunctive": -2.1, "forfeit": -2.5, "violate": -2.4, "violation": -2.4, "infringe": -2.5,
    "infringement": -2.5, "sole discretion": -2.7, "unilateral": -2.5, "disclaim": -2.0,
    "waive": -1.9, "waiver": -1.9, "non-compete": -2.2, "restriction": -1.8, "withhold": -1.7,
    "immediate termination": -2.8, "negligence": -2.3, "misconduct": -2.6, "fraud": -3.0
}

INTENSIFIERS = {
    "strictly": 1.4, "expressly": 1.3, "immediately": 1.4, "severely": 1.5,
    "irrevocably": 1.5, "solely": 1.3, "entirely": 1.2, "unconditionally": 1.4
}

NEGATIONS = {"not", "no", "never", "without", "neither", "nor", "none", "disclaim"}


def analyze_document_sentiment(sentences: List[str]) -> SentimentMetrics:
    """
    Computes sentiment and contractual tone metrics across document sentences.
    Uses legal-aware VADER-style polarity with modifier heuristics.
    """
    if not sentences:
        return SentimentMetrics(
            compound=0.0,
            positive=0.0,
            neutral=1.0,
            negative=0.0,
            tone_label="Neutral",
            tone_explanation="No sentences found to assess tone."
        )

    pos_score_sum = 0.0
    neg_score_sum = 0.0
    neu_score_sum = 0.0
    total_sentence_valence = 0.0

    for sentence in sentences:
        words = re.findall(r'\b[a-zA-Z-]+\b', sentence.lower())
        if not words:
            neu_score_sum += 1.0
            continue

        sent_valence = 0.0
        pos_words = 0
        neg_words = 0

        # Check multi-word lexicon entries first
        sentence_lower = sentence.lower()
        for phrase, weight in LEGAL_POLARITY_LEXICON.items():
            if " " in phrase and phrase in sentence_lower:
                sent_valence += weight
                if weight > 0:
                    pos_words += 1
                else:
                    neg_words += 1

        # Check single-word tokens with negation and intensifier windows
        for i, word in enumerate(words):
            if word in LEGAL_POLARITY_LEXICON and " " not in word:
                val = LEGAL_POLARITY_LEXICON[word]
                
                # Check preceding 3 tokens for intensifiers and negations
                multiplier = 1.0
                is_negated = False
                for prev in words[max(0, i - 3): i]:
                    if prev in INTENSIFIERS:
                        multiplier *= INTENSIFIERS[prev]
                    if prev in NEGATIONS:
                        is_negated = not is_negated

                final_val = -val * 0.7 if is_negated else val * multiplier
                sent_valence += final_val

                if final_val > 0:
                    pos_words += 1
                elif final_val < 0:
                    neg_words += 1

        total_sentence_valence += sent_valence
        total_eval = pos_words + neg_words
        if total_eval == 0:
            neu_score_sum += 1.0
        else:
            pos_score_sum += pos_words / (total_eval + 2)
            neg_score_sum += neg_words / (total_eval + 2)
            neu_score_sum += 2 / (total_eval + 2)

    total_chunks = max(1, len(sentences))
    # Normalized compound valence score using hyperbolic tangent style curve: x / sqrt(x^2 + alpha)
    norm_val = total_sentence_valence / total_chunks
    compound = round(norm_val / math.sqrt(norm_val * norm_val + 15), 3)

    raw_sum = pos_score_sum + neg_score_sum + neu_score_sum
    pos_ratio = round(pos_score_sum / raw_sum, 3) if raw_sum > 0 else 0.1
    neg_ratio = round(neg_score_sum / raw_sum, 3) if raw_sum > 0 else 0.1
    neu_ratio = round(max(0.0, 1.0 - (pos_ratio + neg_ratio)), 3)

    # Tone classification
    if compound <= -0.4:
        tone_label = "Highly Restrictive & Punitive"
        tone_explanation = "The document exhibits heavy punitive clauses, unilateral remedies, and stringent liability assignments."
    elif compound <= -0.15:
        tone_label = "Strict & Risk-Averse"
        tone_explanation = "The document contains high regulatory constraints, disclaimers, and rigorous compliance mandates."
    elif compound >= 0.35:
        tone_label = "Favorable & Protective"
        tone_explanation = "The document contains strong mutual protections, clear benefits, cure periods, and bilateral remedies."
    else:
        tone_label = "Balanced & Neutral"
        tone_explanation = "The document balances rights and obligations with standard commercial and legal stipulations."

    return SentimentMetrics(
        compound=compound,
        positive=pos_ratio,
        neutral=neu_ratio,
        negative=neg_ratio,
        tone_label=tone_label,
        tone_explanation=tone_explanation
    )
