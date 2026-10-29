from app.ingestion.parser import parse_document
from app.models.schemas import PageSpan
from app.structure.segmenter import clause_label, segment_document

CONTRACT = """MASTER SERVICES AGREEMENT

1. Definitions
1.1 "Services" means the hosted software described in the Order Form.
1.2 "Fees" means the amounts payable under the Order Form.

2. Fees and Payment
Customer shall pay all invoices within thirty (30) days of receipt.

3. Limitation of Liability
IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY EXCEED THE FEES PAID IN THE TWELVE MONTHS BEFORE THE CLAIM.
"""


def _segment(text):
    return segment_document(text, [PageSpan(page=1, start=0, end=len(text))])


def test_offsets_point_back_into_the_document():
    for c in _segment(CONTRACT):
        assert CONTRACT[c.start:c.end] == c.text
        assert c.page == 1


def test_numbered_headings_become_clauses():
    labels = [clause_label(c) for c in _segment(CONTRACT)]
    assert any(l.startswith("2") and "Fees and Payment" in l for l in labels)
    assert any(l.startswith("3") and "Limitation of Liability" in l for l in labels)


def test_subclauses_nest_under_their_section():
    clauses = _segment(CONTRACT)
    by_number = {c.number: c for c in clauses if c.number}
    assert "1.1" in by_number and "1" in by_number
    assert by_number["1.1"].parent_id == by_number["1"].id
    assert by_number["1.1"].level > by_number["1"].level


def test_unstructured_text_falls_back_to_paragraphs():
    text = "\n\n".join(f"Paragraph {i} says the provider may do something reasonable with your account data." * 3
                       for i in range(12))
    clauses = _segment(text)
    assert len(clauses) >= 6
    assert all(text[c.start:c.end] == c.text for c in clauses)


def test_empty_text_yields_no_clauses():
    assert _segment("") == []


def test_plain_english_and_sentence_case_headings():
    body = "The Receiver may share the Confidential Information with its Permitted Receivers on a need to know basis."
    text = f"1. Who can I share it with?\n\n{body}\n\n2. Other important information\n\n{body}\n\n(a) independently developed by the Receiver, or\n\n{body}"
    labels = [clause_label(c) for c in _segment(text)]
    assert "1 Who can I share it with?" in labels
    assert "2 Other important information" in labels
    assert not any("independently developed" in l for l in labels)


def test_docx_table_number_cell_joins_its_title():
    import io

    import docx

    document = docx.Document()
    table = document.add_table(rows=2, cols=2)
    for row, (num, title) in zip(table.rows, [("1.", "What is Confidential Information?"), ("2.", "Who can I share it with?")]):
        row.cells[0].text = num
        row.cells[1].text = f"{title}\nConfidential Information means information disclosed by a party in connection with the Purpose."
    buf = io.BytesIO()
    document.save(buf)
    parsed = parse_document(buf.getvalue(), "nda.docx")
    assert "2. Who can I share it with?" in parsed.text and "|" not in parsed.text
    labels = [clause_label(c) for c in segment_document(parsed.text, parsed.pages, parsed.heading_hints)]
    assert "2 Who can I share it with?" in labels


def test_parse_text_normalizes_and_counts_pages():
    parsed = parse_document("The first line of the agreement.\r\n\r\nThe second   line of the agreement.".encode(), "x.txt")
    assert parsed.source_type == "txt"
    assert parsed.page_count == 1
    assert "\r" not in parsed.text
