import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

_ALWAYS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("ACCOUNT", re.compile(r"\b(?:account|a/c|acct)\.?\s*(?:no\.?|number|#)?\s*:?\s*\d{6,18}\b", re.I)),
    ("PHONE", re.compile(r"(?<!\w)(?:\+\d{1,3}[\s-]?)?(?:\(\d{2,4}\)[\s-]?)?\d{3,5}[\s-]\d{3,5}(?:[\s-]\d{2,4})?(?!\w)")),
]
_MONEY = re.compile(r"(?:[$€£₹]|\b(?:Rs\.?|INR|USD|EUR|GBP)\s?)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|lakhs|crore|million|k|m))?", re.I)


@dataclass
class Redactor:
    """Reversible PII redaction applied to text sent to external LLMs."""

    strict: bool = False
    names: Iterable[str] = ()
    mapping: Dict[str, str] = field(default_factory=dict)
    _reverse: Dict[str, str] = field(default_factory=dict)
    _counters: Dict[str, int] = field(default_factory=dict)

    def _token(self, kind: str, value: str) -> str:
        if value in self._reverse:
            return self._reverse[value]
        self._counters[kind] = self._counters.get(kind, 0) + 1
        token = f"[{kind}_{self._counters[kind]}]"
        self.mapping[token] = value
        self._reverse[value] = token
        return token

    def redact(self, text: str) -> str:
        patterns = list(_ALWAYS)
        if self.strict:
            patterns.append(("AMOUNT", _MONEY))
            for name in sorted({n for n in self.names if n and len(n) > 3}, key=len, reverse=True):
                patterns.append(("PARTY", re.compile(re.escape(name), re.I)))
        for kind, pattern in patterns:
            text = pattern.sub(lambda m, k=kind: self._replace(k, m.group(0)), text)
        return text

    def _replace(self, kind: str, value: str) -> str:
        if kind in ("PHONE", "CARD") and sum(c.isdigit() for c in value) < 10:
            return value
        return self._token(kind, value)

    def restore(self, text: str) -> str:
        if not text or not self.mapping:
            return text
        return re.sub(r"\[[A-Z]+_\d+\]", lambda m: self.mapping.get(m.group(0), m.group(0)), text)
