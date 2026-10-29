"""PDF layouts seen in real filings and web policies: running footers, detached clause numbers, styled headings."""
import pymupdf

from app.ingestion.parser import parse_document, reflow_pdf_lines, strip_running_lines
from app.structure.segmenter import clause_label, segment_document

BODY = ("The Employee shall perform such duties and responsibilities as are consistent with the designation "
        "and as may be assigned by the Board from time to time.")


def _pdf(pages):
    """pages: list of [(text, fontname, size)] lines."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 60
        for text, font, size in lines:
            page.insert_text((50, y), text, fontname=font, fontsize=size)
            y += size + 8
    return doc.tobytes()


def test_running_footer_and_page_numbers_are_removed():
    pages = [f"LOGO\n{BODY} Page {n} of the agreement continues with further obligations of each party.\nCIN: U63090KA2012FTC065834\n{n}"
             for n in (1, 2, 3)]
    cleaned = strip_running_lines(pages)
    assert all("CIN" not in p and "LOGO" not in p for p in cleaned)
    assert all(not p.strip().endswith(str(n)) for n, p in zip((1, 2, 3), cleaned))
    assert all(BODY in p for p in cleaned)


def test_detached_clause_numbers_rejoin_their_text():
    text = reflow_pdf_lines(f"2.\nDuties & Responsibilities.\n2.1.\n{BODY}\na.\nBase Salary. The base pay is $100,000.")
    assert "2. Duties & Responsibilities." in text
    assert f"2.1. {BODY}" in text
    assert "a. Base Salary." in text


def test_wrapped_all_caps_notice_stays_one_paragraph():
    notice = ("THESE TERMS CONTAIN A MANDATORY ARBITRATION PROVISION THAT, AS FURTHER SET\n"
              "FORTH IN SECTION 6 BELOW, REQUIRES THE USE OF ARBITRATION ON AN INDIVIDUAL\n"
              "BASIS TO RESOLVE DISPUTES, RATHER THAN JURY TRIALS OR ANY OTHER COURT\n"
              "PROCEEDINGS, OR CLASS ACTIONS OF ANY KIND.")
    text = reflow_pdf_lines(f"{notice}\nService provider\n{BODY}")
    assert "AS FURTHER SET FORTH IN SECTION 6" in text
    assert text.count("\n\n") <= 2


def test_styled_headings_and_run_in_labels_from_a_real_pdf():
    footer = ("ACME Pvt Ltd | CIN: U12345KA2020PTC000001", "helv", 8)
    data = _pdf([
        [("What & Why", "hebo", 11), (BODY, "helv", 11), ("Start Date:", "hebo", 11), (BODY, "helv", 11), footer],
        [("With Whom", "hebo", 11), (BODY, "helv", 11), (BODY, "helv", 11), footer],
        [("Retention", "hebo", 11), (BODY, "helv", 11), footer],
    ])
    parsed = parse_document(data, "policy.pdf")
    assert "CIN" not in parsed.text
    labels = [clause_label(c) for c in segment_document(parsed.text, parsed.pages, parsed.heading_hints)]
    assert {"What & Why", "With Whom", "Retention"} <= set(labels)
