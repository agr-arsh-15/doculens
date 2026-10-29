"""Printable risk report (fpdf2, core fonts only so it works without system libraries)."""
from datetime import datetime
from typing import Dict, List

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.models.schemas import AnalysisResult, Finding, SourceLink

_SEV_RGB = {
    "critical": (178, 34, 34), "high": (214, 96, 36), "medium": (196, 146, 20), "low": (70, 130, 110), "info": (110, 110, 110),
}
_INK = (28, 28, 30)
_MUTED = (100, 100, 105)
_REPLACEMENTS = {
    "\u20b9": "INR ", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": " - ",
    "\u2026": "...", "\u2022": "-", "\u00a0": " ", "\u2264": "<=", "\u2265": ">=", "\u2192": "->", "\u20ac": "EUR ",
}


def _t(text: str | None) -> str:
    if not text:
        return ""
    for k, v in _REPLACEMENTS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class _Report(FPDF):
    def __init__(self, title: str):
        super().__init__(format="A4")
        self.title_text = title
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 16, 18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, _t(f"DocuLens risk report - {self.title_text}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(0, 6, _t(f"Page {self.page_no()}  |  Not legal advice"), align="C")


def _h(pdf: FPDF, text: str, size: int = 13):
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", size)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 7, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _p(pdf: FPDF, text: str, size: float = 10, style: str = "", color=_INK, height: float = 5):
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, height, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


class _Citations:
    """Numbers each distinct source in order of first use, for [n] markers and the closing Sources list."""

    def __init__(self):
        self.order: List[SourceLink] = []
        self._index: Dict[str, int] = {}

    def mark(self, links: List[SourceLink]) -> str:
        nums = []
        for link in links:
            key = link.id or link.url or link.title
            if key not in self._index:
                self.order.append(link)
                self._index[key] = len(self.order)
            nums.append(self._index[key])
        return "".join(f"[{n}]" for n in nums)


def _ai_only(f: Finding) -> bool:
    return "llm" in f.sources and "rule" not in f.sources


def _finding(pdf: FPDF, f: Finding, cites: _Citations):
    if pdf.get_y() > 250:
        pdf.add_page()
    r, g, b = _SEV_RGB[f.severity]
    pdf.set_fill_color(r, g, b)
    y = pdf.get_y()
    pdf.rect(pdf.l_margin, y + 1, 2.2, 5, style="F")
    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*_INK)
    tag = f"[{f.severity.upper()}{' - HIDDEN' if f.kind == 'hidden' else ''}{' - MISSING' if f.kind == 'missing' else ''}]"
    pdf.multi_cell(0, 6, _t(f"{f.id}  {tag}  {f.title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    meta = " | ".join(x for x in [f.clause_label, f"confidence {int(f.confidence * 100)}%", ", ".join(f.sources),
                                  "verified quote" if f.verified else None] if x)
    _p(pdf, meta, size=8, color=_MUTED, height=4)
    if f.quote:
        pdf.set_x(pdf.l_margin + 4)
        _p(pdf, f'"{f.quote[:600]}"', size=9, style="I", color=(70, 70, 75), height=4.6)
    if f.explanation:
        _p(pdf, (f"AI explanation: {f.explanation}" if _ai_only(f) else f.explanation), size=9.5)
    if f.hidden_reason:
        _p(pdf, f"Why it is easy to miss: {f.hidden_reason}", size=9, color=_MUTED)
    linked = [r for r in f.references if r.url]
    if f.market_comparison:
        marks = cites.mark(linked)
        _p(pdf, f"Market standard: {f.market_comparison} {marks}".rstrip(), size=9, color=_MUTED)
    elif linked:
        _p(pdf, f"Sources: {cites.mark(linked)}", size=8, color=_MUTED)
    if f.ai_comparison:
        _p(pdf, f"AI comparison (not sourced): {f.ai_comparison}", size=9, color=_MUTED)
    if f.recommendation:
        _p(pdf, f"Recommendation: {f.recommendation}", size=9.5, style="B")
    if f.redline:
        _p(pdf, f"Suggested wording: {f.redline.suggested}", size=9, color=(20, 90, 60))
    pdf.ln(3)


def _sources_section(pdf: FPDF, cites: _Citations):
    if not cites.order:
        return
    _h(pdf, "Sources", 11)
    for n, link in enumerate(cites.order, 1):
        _p(pdf, f"[{n}] {link.title}" + (f" - {link.publisher}" if link.publisher else ""), size=8.5, height=4.4)
        if link.url:
            pdf.set_font("Helvetica", "U", 7.5)
            pdf.set_text_color(30, 80, 160)
            pdf.write(4, _t(link.url), link=link.url)
            pdf.ln(5)


def build_report_pdf(result: AnalysisResult) -> bytes:
    pdf = _Report(result.filename)
    pdf.add_page()
    card = result.scorecard

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5, "DOCULENS  |  DOCUMENT RISK REPORT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 9, _t(result.filename), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    created = result.created_at[:19].replace("T", " ")
    _p(pdf, f"{result.doc_type_label}  |  {result.jurisdiction_label}  |  Read as: {result.perspective_label}  |  {created} UTC",
       size=9, color=_MUTED)
    pdf.ln(4)

    y = pdf.get_y()
    pdf.set_fill_color(245, 241, 232)
    pdf.rect(pdf.l_margin, y, 174, 30, style="F")
    pdf.set_xy(pdf.l_margin + 6, y + 4)
    pdf.set_font("Helvetica", "B", 30)
    pdf.cell(28, 14, _t(card.grade))
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(60, 8, _t(f"Score {card.overall}/100"), new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_xy(pdf.l_margin + 34, y + 13)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(80, 6, _t(f"Risk level: {card.risk_level}"))
    pdf.set_xy(pdf.l_margin + 34, y + 19)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_MUTED)
    counts = {}
    for f in result.findings:
        if not f.favorable:
            counts[f.severity] = counts.get(f.severity, 0) + 1
    pdf.cell(0, 6, _t("  ".join(f"{k}: {counts[k]}" for k in ["critical", "high", "medium", "low"] if k in counts) or "No risks found"))
    pdf.set_y(y + 34)

    _h(pdf, "Summary")
    _p(pdf, result.summary, size=10)

    _h(pdf, "Category scores")
    pdf.set_font("Helvetica", "", 9.5)
    for c in card.categories:
        pdf.set_text_color(*_INK)
        pdf.cell(55, 6, _t(c.label))
        bar_y = pdf.get_y() + 1.5
        pdf.set_fill_color(230, 226, 218)
        pdf.rect(pdf.get_x(), bar_y, 90, 3, style="F")
        color = (46, 125, 90) if c.score >= 80 else (196, 146, 20) if c.score >= 55 else (178, 34, 34)
        pdf.set_fill_color(*color)
        pdf.rect(pdf.get_x(), bar_y, 90 * c.score / 100, 3, style="F")
        pdf.set_x(pdf.get_x() + 95)
        pdf.cell(0, 6, f"{c.score}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    by_id = {f.id: f for f in result.findings}
    top = [by_id[i] for i in card.top_negotiation if i in by_id]
    if top:
        _h(pdf, "Top things to negotiate")
        for i, f in enumerate(top, 1):
            _p(pdf, f"{i}. {f.title}: {f.recommendation or (f.redline.suggested if f.redline else '')}", size=10)

    cites = _Citations()
    risks = [f for f in result.findings if not f.favorable]
    if risks:
        pdf.add_page()
        _h(pdf, f"Findings ({len(risks)})", 15)
        for f in risks:
            _finding(pdf, f, cites)

    if result.benchmarks:
        _h(pdf, "Market benchmarks")
        for b in result.benchmarks:
            marks = cites.mark([s for s in b.sources if s.url])
            _p(pdf, f"- {b.note} Assessment: {b.assessment}. {marks}".rstrip(), size=9.5)

    favorable = [f for f in result.findings if f.favorable]
    if favorable:
        _h(pdf, "Terms that favor you")
        for f in favorable[:12]:
            _p(pdf, f"- {f.title}" + (f" ({f.clause_label})" if f.clause_label else ""), size=9.5)

    _sources_section(pdf, cites)

    _h(pdf, "Method", 11)
    e = result.engine
    mode = f"Hybrid: rules + embeddings ({e.embedding_backend}) + LLM ({e.llm_provider}:{e.llm_model})" if e.mode == "hybrid" \
        else f"Local: rules + embeddings ({e.embedding_backend}); no LLM"
    _p(pdf, f"{mode}. Playbook {result.doc_type}@{result.playbook_version}, prompt {result.prompt_version}. "
            f"{card.formula}", size=8.5, color=_MUTED)
    for w in e.warnings:
        _p(pdf, f"Note: {w}", size=8.5, color=_MUTED)
    pdf.ln(2)
    _p(pdf, result.disclaimer, size=8.5, style="I", color=_MUTED)
    _p(pdf, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", size=7.5, color=_MUTED)
    return bytes(pdf.output())
