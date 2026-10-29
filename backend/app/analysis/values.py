import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

_UNITS_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS_WORDS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUM_WORD = r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|a hundred|one hundred|hundred)"

_DURATION = re.compile(
    rf"(?P<num>\d+(?:\.\d+)?|{_NUM_WORD})(?:\s*\((?P<paren>\d+(?:\.\d+)?)\))?[\s-]*"
    r"(?P<unit>(?:calendar|business|working)\s+days?|days?|weeks?|months?|years?|yrs?|hours?|hrs?)\b",
    re.I,
)
_PERCENT = re.compile(r"(?P<num>\d{1,3}(?:\.\d+)?)\s?(?:%|percent\b|per cent\b)", re.I)
_MONEY = re.compile(
    r"(?P<cur>[$€£₹]|\b(?:Rs\.?|INR|USD|EUR|GBP)\s?)\s?(?P<num>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<scale>lakhs?|crores?|million|billion|k)\b)?",
    re.I,
)

_TO_DAYS = {"day": 1.0, "business day": 1.4, "working day": 1.4, "calendar day": 1.0, "week": 7.0, "month": 30.0,
            "year": 365.0, "hour": 1 / 24}


@dataclass
class ExtractedValue:
    value: float
    unit: str
    raw: str
    start: int
    end: int


def word_to_number(token: str) -> Optional[float]:
    t = token.lower().strip()
    try:
        return float(t)
    except ValueError:
        pass
    if t in ("hundred", "a hundred", "one hundred"):
        return 100.0
    parts = re.split(r"[- ]", t)
    total = 0
    for p in parts:
        if p in _TENS_WORDS:
            total += _TENS_WORDS[p]
        elif p in _UNITS_WORDS:
            total += _UNITS_WORDS[p]
        else:
            return None
    return float(total)


def _unit_key(unit: str) -> str:
    u = unit.lower().rstrip("s")
    if u in ("yr", "year"):
        return "year"
    if u in ("hr", "hour"):
        return "hour"
    if u.endswith("day"):
        return u if " " in u else "day"
    return u


def convert_duration(value: float, unit: str, target: str) -> float:
    key = _unit_key(unit)
    exact = {("year", "months"): 12.0, ("month", "years"): 1 / 12, ("year", "years"): 1.0, ("month", "months"): 1.0,
             ("week", "months"): 12 / 52, ("week", "years"): 1 / 52}
    if (key, target) in exact:
        return value * exact[(key, target)]
    days = value * _TO_DAYS.get(key, 1.0)
    if target == "days":
        return days
    if target == "months":
        return days / 30.0
    if target == "years":
        return days / 365.0
    if target == "hours":
        return days * 24.0
    return days


def find_durations(text: str, offset: int = 0) -> List[ExtractedValue]:
    out: List[ExtractedValue] = []
    for m in _DURATION.finditer(text):
        raw_num = m.group("paren") or m.group("num")
        num = word_to_number(raw_num)
        if num is None or num <= 0 or num > 10000:
            continue
        out.append(ExtractedValue(value=num, unit=_unit_key(m.group("unit")), raw=m.group(0).strip(),
                                  start=offset + m.start(), end=offset + m.end()))
    return out


def find_percents(text: str, offset: int = 0) -> List[ExtractedValue]:
    return [ExtractedValue(value=float(m.group("num")), unit="percent", raw=m.group(0), start=offset + m.start(),
                           end=offset + m.end()) for m in _PERCENT.finditer(text)]


def find_money(text: str, offset: int = 0) -> List[ExtractedValue]:
    out: List[ExtractedValue] = []
    for m in _MONEY.finditer(text):
        try:
            value = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        scale = (m.group("scale") or "").lower()
        value *= {"lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7, "million": 1e6, "billion": 1e9, "k": 1e3}.get(scale, 1)
        out.append(ExtractedValue(value=value, unit=m.group("cur").strip(), raw=m.group(0).strip(),
                                  start=offset + m.start(), end=offset + m.end()))
    return out


def sentence_bounds(text: str, start: int, end: int) -> tuple:
    """Expand [start, end) to the enclosing sentence within text."""
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start), text.rfind("; ", 0, start))
    s = 0 if left == -1 else left + 1
    candidates = [i for i in (text.find(". ", end), text.find("\n", end)) if i != -1]
    e = min(candidates) + 1 if candidates else len(text)
    while s < len(text) and text[s] in " \n":
        s += 1
    return s, max(s, min(e, len(text)))


def value_near_context(text: str, values: Iterable[ExtractedValue], context: List[str], offset: int = 0,
                       exclude: Optional[List[str]] = None,
                       prefer: Optional[List[str]] = None) -> Optional[ExtractedValue]:
    """First value whose sentence mentions one of the context stems and none of the exclusions.

    Sentences that mention a `prefer` stem win over earlier sentences that do not."""
    lower = text.lower()
    best: Optional[ExtractedValue] = None
    best_key = None
    for v in values:
        s, e = sentence_bounds(text, v.start - offset, v.end - offset)
        sentence = lower[s:e]
        if exclude and any(x in sentence for x in exclude):
            continue
        if not context:
            return v
        distances = []
        for c in context:
            for m in re.finditer(re.escape(c), sentence):
                ctx_pos = s + m.start()
                distances.append(abs(ctx_pos - (v.start - offset)))
        if not distances:
            continue
        preferred = bool(prefer) and any(p in sentence for p in prefer)
        key = (not preferred, s, min(distances))
        if best_key is None or key < best_key:
            best, best_key = v, key
    return best
