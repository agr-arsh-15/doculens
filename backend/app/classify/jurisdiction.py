import re
from collections import defaultdict
from typing import Dict, List, Tuple

JURISDICTION_LABELS: Dict[str, str] = {
    "IN": "India",
    "US": "United States",
    "EU": "European Union",
    "UK": "United Kingdom",
    "SG": "Singapore",
    "GLOBAL": "Unspecified / International",
}

_SIGNALS: Dict[str, List[Tuple[str, float]]] = {
    "IN": [
        (r"\bindia\b|\bindian\b", 2.0), (r"₹|\brs\.?\s?\d|\binr\b", 2.0), (r"\blakhs?\b|\bcrores?\b", 2.0),
        (r"\b(bengaluru|bangalore|mumbai|new delhi|delhi|hyderabad|chennai|pune|gurugram|gurgaon|noida|kolkata|ahmedabad)\b", 1.5),
        (r"companies act,? 2013|dpdp|digital personal data protection|information technology act|indian contract act", 3.0),
        (r"\bctc\b|cost to company|provident fund|\bpf\b|gratuity|\bhra\b", 1.5), (r"\bpvt\.? ltd\b|private limited", 1.5),
    ],
    "US": [
        (r"united states|\bu\.s\.a?\b|\busa\b", 2.0), (r"\$\s?\d|\busd\b", 1.0), (r"401\(k\)|at[- ]will|\bw-2\b|\bfica\b", 2.0),
        (r"\b(delaware|california|new york|texas|washington|massachusetts|illinois|florida|colorado)\b", 1.5),
        (r"\bccpa\b|\bcpra\b|\bhipaa\b|\bflsa\b|\bcoppa\b", 2.0), (r"\binc\.|\bllc\b|\bcorp\.", 0.5),
    ],
    "EU": [
        (r"\bgdpr\b|general data protection regulation|regulation \(eu\) 2016/679", 3.0),
        (r"european union|\beea\b|\beu\b|supervisory authority|standard contractual clauses", 2.0), (r"€|\beur\b", 1.5),
        (r"\b(germany|france|ireland|netherlands|spain|italy|belgium|sweden|luxembourg|dublin|berlin|paris|amsterdam)\b", 1.5),
        (r"\bgmbh\b|\bs\.a\.\b|\bb\.v\.\b", 1.0),
    ],
    "UK": [
        (r"england and wales|united kingdom|\buk gdpr\b|\bscotland\b", 3.0), (r"£|\bgbp\b", 1.5), (r"\blondon\b|\bmanchester\b", 1.0),
        (r"\bltd\b(?!.{0,5}pvt)|companies house|data protection act 2018", 0.8),
    ],
    "SG": [(r"\bsingapore\b|\bpdpa\b|\bsgd\b|\bpte\.? ltd\b", 2.5)],
}

_GOVERNING_LAW = re.compile(
    r"(?:governed by|construed in accordance with|subject to)[^.]{0,60}?laws? of\s+(?:the\s+)?([^.;,\n]{2,60})", re.I
)
_LAW_TO_CODE = [
    (r"india|karnataka|maharashtra|delhi|tamil nadu|telangana", "IN"),
    (r"united states|state of|delaware|california|new york|texas|washington|massachusetts", "US"),
    (r"england|wales|united kingdom|scotland", "UK"),
    (r"ireland|germany|france|netherlands|european|luxembourg|spain|italy", "EU"),
    (r"singapore", "SG"),
]


def detect_jurisdiction(text: str) -> Tuple[str, List[str]]:
    lower = text.lower()
    scores: Dict[str, float] = defaultdict(float)
    evidence: List[str] = []

    for m in _GOVERNING_LAW.finditer(text):
        target = m.group(1).lower()
        for pattern, code in _LAW_TO_CODE:
            if re.search(pattern, target):
                scores[code] += 8.0
                evidence.append(m.group(0).strip()[:120])
                break

    for code, signals in _SIGNALS.items():
        for pattern, weight in signals:
            hits = len(re.findall(pattern, lower))
            if hits:
                scores[code] += weight * min(hits, 4)
                if len(evidence) < 5 and weight >= 2.0:
                    sample = re.search(pattern, lower)
                    if sample:
                        evidence.append(f"mentions '{text[sample.start():sample.end()]}'")

    if not scores:
        return "GLOBAL", []
    best = max(scores, key=scores.get)
    if scores[best] < 3.0:
        return "GLOBAL", evidence[:5]
    return best, evidence[:5]
