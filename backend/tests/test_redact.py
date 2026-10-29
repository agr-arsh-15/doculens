from app.llm.redact import Redactor

TEXT = ("Contact priya.sharma@example.com or +91 98765 43210. PAN ABCDE1234F. "
        "Nimbus Softech Private Limited will pay Rs. 9,60,000 per year.")


def test_identifiers_are_always_redacted_and_restorable():
    r = Redactor()
    redacted = r.redact(TEXT)
    for secret in ("priya.sharma@example.com", "ABCDE1234F", "98765 43210"):
        assert secret not in redacted
    assert "Rs. 9,60,000" in redacted
    assert r.restore(redacted) == TEXT


def test_strict_mode_also_hides_parties_and_amounts():
    r = Redactor(strict=True, names=["Nimbus Softech Private Limited"])
    redacted = r.redact(TEXT)
    assert "Nimbus Softech" not in redacted
    assert "9,60,000" not in redacted
    assert r.restore(redacted) == TEXT


def test_same_value_reuses_token():
    r = Redactor()
    out = r.redact("a@b.co then a@b.co again")
    assert out.count("[EMAIL_1]") == 2


def test_short_numbers_are_not_mistaken_for_phones():
    assert Redactor().redact("Notice of 90 days and 2 years.") == "Notice of 90 days and 2 years."
