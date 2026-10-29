import re
from typing import List
from app.lab.schemas import ReadabilityMetrics


def count_syllables_in_word(word: str) -> int:
    """Heuristic syllable counter for an English word."""
    w = word.lower().strip()
    if len(w) <= 3:
        return 1

    # Remove non-alphabetic
    w = re.sub(r'[^a-z]', '', w)
    if not w:
        return 1

    # Discard common endings that don't add syllables
    if w.endswith('e') and not w.endswith('le') and len(w) > 3:
        w = w[:-1]

    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    for char in w:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    return max(1, count)


def compute_readability_metrics(sentences: List[str], tokens: List[str]) -> ReadabilityMetrics:
    """
    Computes standard computational linguistics readability metrics:
    - Flesch Reading Ease
    - Flesch-Kincaid Grade Level
    - Gunning Fog Index
    - Average words per sentence, syllables per word, reading time
    """
    total_sentences = max(1, len(sentences))
    words = [t for t in tokens if re.match(r'^[a-zA-Z]+$', t)]
    total_words = max(1, len(words))

    syllable_counts = [count_syllables_in_word(w) for w in words]
    total_syllables = sum(syllable_counts)

    # Complex words have 3 or more syllables
    complex_words = sum(1 for s in syllable_counts if s >= 3)

    asl = total_words / total_sentences  # Average Sentence Length
    asw = total_syllables / total_words  # Average Syllables per Word

    # Flesch Reading Ease formula
    fre = 206.835 - (1.015 * asl) - (84.6 * asw)
    fre = max(0.0, min(100.0, fre))

    # Flesch-Kincaid Grade Level
    fkgl = (0.39 * asl) + (11.8 * asw) - 15.59
    fkgl = max(1.0, fkgl)

    # Gunning Fog Index
    pct_complex = (complex_words / total_words) * 100.0
    gunning_fog = 0.4 * (asl + pct_complex)

    # Reading time (approx 200 words per minute)
    read_time = round(total_words / 200.0, 1)

    # Qualitative complexity rating
    if fre < 30.0:
        complexity = "Extremely Dense / Postgraduate Legal Text"
    elif fre < 50.0:
        complexity = "Difficult / Professional Grade"
    elif fre < 65.0:
        complexity = "Moderate / High School Standard"
    else:
        complexity = "Clear / Plain Language"

    return ReadabilityMetrics(
        flesch_reading_ease=round(fre, 1),
        flesch_kincaid_grade=round(fkgl, 1),
        gunning_fog_index=round(gunning_fog, 1),
        avg_words_per_sentence=round(asl, 1),
        avg_syllables_per_word=round(asw, 2),
        estimated_read_time_minutes=read_time,
        complexity_level=complexity
    )
