import pytest

from app.lab import tokenizer

TEXT = """LETTER OF APPOINTMENT

1. Compensation
Your annual CTC will be Rs. 9,60,000 (Rupees Nine Lakh only). It includes a variable component.

2. Notice
See Sec. 4 of the policy, e.g. the HR handbook. Resignation needs 60 days notice.
"""


@pytest.fixture(params=["nltk", "regex"])
def segment(request, monkeypatch):
    if request.param == "regex":
        monkeypatch.setattr(tokenizer, "_nltk_tokenizers", lambda: (None, None))
    elif tokenizer._nltk_tokenizers()[0] is None:
        pytest.skip("NLTK punkt data not installed")
    return tokenizer.segment_sentences


def test_headings_are_separate_sentences(segment):
    sentences = segment(TEXT)
    assert sentences[0] == "LETTER OF APPOINTMENT"
    assert "1. Compensation" in sentences


def test_abbreviations_do_not_split_sentences(segment):
    sentences = segment(TEXT)
    assert any(s.startswith("Your annual CTC will be Rs. 9,60,000") for s in sentences)
    assert any("Sec. 4 of the policy, e.g. the HR handbook." in s for s in sentences)
