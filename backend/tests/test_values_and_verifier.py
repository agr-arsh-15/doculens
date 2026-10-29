import pytest

from app.analysis.values import convert_duration, find_durations, find_money, find_percents
from app.analysis.verifier import locate_quote, verify_in_clause_or_document

DOC = ("Your annual Cost to Company (CTC) will be Rs. 9,60,000. You shall give ninety (90) days written notice. "
       "The variable component of 15% will be paid at the \u201csole discretion\u201d of the management.")


def test_durations_read_words_and_digits():
    values = find_durations("give ninety (90) days notice and serve two (2) years")
    assert [(v.value, v.unit.rstrip("s")) for v in values][:2] == [(90, "day"), (2, "year")]


@pytest.mark.parametrize("value,unit,target,expected", [(2, "years", "months", 24), (6, "months", "days", 180),
                                                        (7, "days", "hours", 168)])
def test_duration_conversion(value, unit, target, expected):
    assert convert_duration(value, unit, target) == pytest.approx(expected, rel=0.01)


def test_money_and_percent_extraction():
    assert find_money("liquidated damages of Rs. 2,00,000 towards training")
    assert find_money("not exceed fifty dollars ($50.00 USD)")
    assert [v.value for v in find_percents("a variable component of 15%")] == [15]


def test_exact_quote_is_located_with_offsets():
    quote = "ninety (90) days written notice"
    start, end, score = locate_quote(quote, DOC)
    assert DOC[start:end] == quote
    assert score == 100.0


def test_whitespace_curly_quotes_and_ellipsis_are_tolerated():
    assert locate_quote('paid at the "sole   discretion" of the management', DOC) is not None
    assert locate_quote("You shall give ninety (90) days written notice...", DOC) is not None


NONCOMPETE = ("b. Employee hereby covenants and agrees that during his employment with the Company, the Employee will not "
              "directly or indirectly, whether individually or through any entity, engage in any business activity which "
              "is competitive with the existing business of the Company. Deductions are made on a pro-rata basis.")


def test_abridged_quote_spans_its_fragments_in_order():
    start, end, _ = locate_quote("...Employee will not ... engage in any business activity ... which is competitive with the "
                                 "existing business of the Company.", NONCOMPETE)
    assert NONCOMPETE[start:end].startswith("Employee will not directly")
    assert NONCOMPETE[start:end].endswith("existing business of the Company.")


def test_abridged_quote_with_an_invented_fragment_falls_back_to_its_head_or_is_rejected():
    assert locate_quote("Employee ... may never work again ... anywhere", NONCOMPETE) is None


def test_typographic_hyphens_match_plain_ones():
    hit = locate_quote("Deductions are made on a pro\u2011rata basis", NONCOMPETE)
    assert hit is not None and NONCOMPETE[hit[0]:hit[1]] == "Deductions are made on a pro-rata basis"


def test_near_verbatim_quote_passes_fuzzy_match():
    assert locate_quote("The variable component of 15% will be paid at the sole discretion of management", DOC)


@pytest.mark.parametrize("quote", [
    "The employee may resign at any time without notice.",
    "Rs. 5,00,000 joining bonus",
    "short",
    "",
])
def test_fabricated_or_trivial_quotes_are_rejected(quote):
    assert locate_quote(quote, DOC) is None


def test_clause_then_document_fallback_returns_absolute_offsets():
    clause_text = "Unrelated clause text about governing law."
    hit = verify_in_clause_or_document("ninety (90) days written notice", clause_text, 500, DOC)
    assert hit is not None and DOC[hit[0]:hit[1]] == "ninety (90) days written notice"
