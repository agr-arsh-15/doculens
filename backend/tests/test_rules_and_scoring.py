from app.analysis.rules import run_rules
from app.analysis.scoring import _grade, score_findings
from app.models.schemas import Finding

NDA = """MUTUAL NON-DISCLOSURE AGREEMENT

1. Confidential Information
"Confidential Information" means non-public information marked as confidential.

2. Exclusions
Confidential Information does not include information that is publicly known or independently developed.

3. Term
Confidentiality obligations survive for three (3) years.
"""

NDA_WITH_LEGAL_CARVEOUT = NDA + """
4. Required Disclosure
The Receiving Party may disclose Confidential Information as required by law or court order, after prompt notice.
"""

OFFER = """OFFER LETTER

1. Variable Pay
The variable component will be paid at the sole discretion of the management.

2. Governing Law
Any dispute shall be referred to arbitration by a sole arbitrator appointed by the Company.
"""


def _titles(findings):
    return [f.title for f in findings]


def test_red_flag_fires_for_the_party_at_risk(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employee", jurisdiction="IN")
    findings = run_rules(ctx)
    arb = next(f for f in findings if "sole arbitrator" in f.title)
    assert not arb.favorable and arb.severity == "high"
    assert "Indian courts" in arb.explanation
    assert arb.quote.startswith("Any dispute shall be referred")


def test_same_clause_is_favorable_from_the_other_side(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employer", jurisdiction="IN")
    arb = next(f for f in run_rules(ctx) if "sole arbitrator" in f.title)
    assert arb.favorable and arb.severity == "info"


def test_document_scoped_exclusion_looks_beyond_the_matched_clause(context_factory):
    without = run_rules(context_factory(NDA, "nda", perspective="receiving"))
    with_carveout = run_rules(context_factory(NDA_WITH_LEGAL_CARVEOUT, "nda", perspective="receiving"))
    assert "No carve-out for disclosures required by law" in _titles(without)
    assert "No carve-out for disclosures required by law" not in _titles(with_carveout)


def test_quotes_never_include_the_heading_line(context_factory):
    text = ("OFFER LETTER\n\n8. Company Policies\nYou will be governed by the rules and policies of the Company "
            "as amended from time to time.\n")
    ctx = context_factory(text, "offer_letter", perspective="employee")
    hidden = [f for f in run_rules(ctx) if "polic" in f.title.lower()]
    assert hidden and not hidden[0].quote.startswith("Company Policies")


def test_clipped_quotes_start_and_end_on_whole_words(context_factory):
    filler = " ".join(f"word{i}" for i in range(120))
    text = f"Restrictions\nThe Executive shall not {filler} compete with the Company {filler} in any territory.\n"
    ctx = context_factory(text, "employment_agreement", perspective="employee")
    start = text.index("compete")
    quote, q_start, q_end = ctx.sentence_quote(start, start + 7)
    assert "compete" in quote and len(quote) <= 420
    assert text[q_start - 1] == " " and text[q_end] == " "


def _finding(severity, favorable=False, kind="risk", confidence=1.0):
    return Finding(id=f"f-{severity}-{favorable}", kind=kind, severity=severity, title=severity, confidence=confidence,
                   favorable=favorable, category="financial", recommendation="fix it")


def test_scores_fall_with_severity_and_ignore_favorable_terms(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employee")
    clean = score_findings(ctx, []).overall
    one_high = score_findings(ctx, [_finding("high")]).overall
    one_critical = score_findings(ctx, [_finding("critical")]).overall
    with_favorable = score_findings(ctx, [_finding("high"), _finding("high", favorable=True)]).overall
    assert clean == 100
    assert clean > one_high > one_critical
    assert with_favorable == one_high


def test_missing_clauses_weigh_less_than_present_risks(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employee")
    assert score_findings(ctx, [_finding("medium", kind="missing")]).overall > score_findings(ctx, [_finding("medium")]).overall


def test_many_minor_findings_do_not_zero_the_score(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employee")
    many_medium = [_finding("medium") for _ in range(30)]
    assert 35 < score_findings(ctx, many_medium).overall < score_findings(ctx, many_medium[:5]).overall


def test_top_negotiation_items_are_the_heaviest(context_factory):
    ctx = context_factory(OFFER, "offer_letter", perspective="employee")
    findings = [_finding("low"), _finding("critical"), _finding("medium")]
    card = score_findings(ctx, findings)
    assert card.top_negotiation[0] == "f-critical-False"


def test_penalty_of_perjury_is_not_an_exit_penalty(context_factory):
    from app.analysis.hidden_risks import detect_survival_and_penalties

    text = ("Verification\nTo verify your identity, we may ask you to give a declaration as to your identity under penalty "
            "of perjury before we act on a privacy request.\n")
    ctx = context_factory(text, "privacy_policy", perspective="user")
    assert not [f for f in detect_survival_and_penalties(ctx) if "penalty" in f.title.lower()]


def test_negated_forfeiture_is_not_a_penalty(context_factory):
    from app.analysis.hidden_risks import detect_survival_and_penalties

    text = ("Severance\nThe mere assertion of claims arising from mandatory provisions of law shall not trigger any reduction "
            "or forfeiture of Severance Benefits.\n")
    ctx = context_factory(text, "employment_agreement", perspective="employee")
    assert not detect_survival_and_penalties(ctx)


def test_identical_wording_in_two_places_is_one_finding():
    from app.analysis.merge import merge_findings

    quote = "you grant us a worldwide, royalty-free, perpetual, irrevocable licence to Your Content"
    us, eu = (Finding(id=f"x{i}", kind="risk", severity="high", title="Perpetual, irrevocable licence to your content",
                      category="legal_exposure", clause_ids=[cid], quote=quote, quote_start=start, quote_end=start + len(quote),
                      sources=["rule"]) for i, (cid, start) in enumerate([("C5", 100), ("C40", 9000)]))
    merged = merge_findings([us, eu])
    assert len(merged) == 1 and merged[0].clause_ids == ["C5", "C40"]


def test_reviewer_and_rule_on_the_same_sentence_merge():
    from app.analysis.merge import merge_findings

    quote = "If you voluntarily resign within twelve months you must repay the sign-on bonus in full."
    llm = Finding(id="a", kind="hidden", severity="high", title="Sign-on bonus repayment", category="financial",
                  clause_ids=["C4"], quote=quote, quote_start=10, quote_end=10 + len(quote), sources=["llm"], clause_type="bonus")
    rule = Finding(id="b", kind="hidden", severity="high", title="Service bond or early-exit penalty", category="financial",
                   clause_ids=["C4"], quote=quote, quote_start=10, quote_end=10 + len(quote), sources=["rule"],
                   clause_type="service_bond")
    merged = merge_findings([rule, llm])
    assert len(merged) == 1 and set(merged[0].sources) == {"llm", "rule"}


def test_missing_item_dropped_when_reviewer_reports_it_absent():
    from app.analysis.merge import merge_findings

    reviewer = Finding(id="a", kind="hidden", severity="high", title="No Severance or Notice Period", category="career_mobility",
                       clause_ids=["C2"], quote="All employment with the Company is at-will.", quote_start=0, quote_end=42,
                       sources=["llm"], clause_type="termination")
    missing = Finding(id="b", kind="missing", severity="medium", title="Missing: Notice Period & Resignation",
                      category="career_mobility", sources=["playbook"], clause_type="notice_period")
    assert [f.title for f in merge_findings([reviewer, missing])] == ["No Severance or Notice Period"]


def test_grade_boundaries():
    assert [_grade(s) for s in (100, 85, 84, 70, 55, 40, 39)] == ["A", "A", "B", "B", "C", "D", "F"]
