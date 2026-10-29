import time
from datetime import datetime, timezone
from typing import Callable, List, Optional

from app.analysis.benchmark import run_benchmarks
from app.analysis.context import AnalysisContext
from app.analysis.hidden_risks import detect_missing_clauses, mark_buried, run_hidden_detectors
from app.analysis.llm_reasoner import run_llm_reasoning
from app.analysis.mapping import map_clauses
from app.analysis.merge import merge_findings
from app.analysis.rules import run_rules
from app.analysis.scoring import score_findings
from app.analysis.summary import build_summary
from app.classify.jurisdiction import JURISDICTION_LABELS
from app.config import DISCLAIMER, PROMPT_VERSION
from app.llm.provider import LLMProvider, get_provider
from app.llm.redact import Redactor
from app.models.schemas import AnalysisResult, Clause, EngineStats, Finding, Party
from app.nlp.embeddings import embedder
from app.playbooks.loader import get_playbook

ProgressFn = Callable[[str, str, int], None]

STAGES = [
    ("mapping", "Mapping clauses to the playbook"),
    ("rules", "Running playbook rules"),
    ("reasoning", "AI clause reasoning"),
    ("verifying", "Verifying evidence quotes"),
    ("hidden", "Hunting for hidden risks"),
    ("benchmarking", "Comparing against market standards"),
    ("scoring", "Scoring and summarizing"),
]


def run_analysis(
    *,
    analysis_id: str,
    document_id: str,
    filename: str,
    text: str,
    clauses: List[Clause],
    parties: List[Party],
    doc_type: str,
    perspective: Optional[str],
    jurisdiction: str,
    use_llm: bool,
    privacy_mode: bool,
    progress: Optional[ProgressFn] = None,
    provider: Optional[LLMProvider] = None,
    notices: Optional[List[str]] = None,
) -> AnalysisResult:
    report = progress or (lambda stage, label, pct: None)
    timings = {}
    playbook = get_playbook(doc_type)
    persp = playbook.perspective(perspective)
    ctx = AnalysisContext(text=text, clauses=[c.model_copy(deep=True) for c in clauses], playbook=playbook,
                          perspective=persp, jurisdiction=jurisdiction)
    if provider is None and use_llm:
        provider = get_provider()
    redactor = Redactor(strict=privacy_mode, names=[p.name.split(' ("')[0] for p in parties])
    warnings: List[str] = list(notices or [])

    def stage(key: str, pct: int):
        label = dict(STAGES)[key]
        report(key, label, pct)
        return time.perf_counter()

    t = stage("mapping", 8)
    map_clauses(ctx)
    timings["mapping"] = (time.perf_counter() - t) * 1000

    t = stage("rules", 18)
    rule_findings = run_rules(ctx)
    timings["rules"] = (time.perf_counter() - t) * 1000

    llm_findings: List[Finding] = []
    llm_stats = None
    if provider is not None:
        t = stage("reasoning", 25)

        def on_batch(done: int, total: int):
            report("reasoning", f"AI clause reasoning ({done}/{total} batches)", 25 + int(45 * done / max(1, total)))

        llm_findings, llm_stats = run_llm_reasoning(ctx, provider, redactor, on_batch)
        timings["reasoning"] = (time.perf_counter() - t) * 1000
        if llm_stats.stopped_reason:
            warnings.append(llm_stats.stopped_reason)
        elif llm_stats.failed_batches:
            warnings.append(f"{llm_stats.failed_batches} of {llm_stats.batches} AI batches failed; those clauses were analyzed by rules only.")
        elif llm_stats.reviewed_clauses < len([c for c in ctx.clauses if len(c.text) >= 40]):
            warnings.append(f"AI reviewed the {llm_stats.reviewed_clauses} highest-priority of {len(ctx.clauses)} clauses "
                            "to keep the analysis fast; every clause was still checked by the rules.")
        stage("verifying", 72)
    elif use_llm:
        warnings.append("No LLM API key configured: ran in local mode (rules + embeddings). Add GROQ_API_KEY or GEMINI_API_KEY for deeper AI reasoning.")

    t = stage("hidden", 78)
    hidden_findings = run_hidden_detectors(ctx)
    timings["hidden"] = (time.perf_counter() - t) * 1000

    t = stage("benchmarking", 85)
    benchmarks, bench_findings = run_benchmarks(ctx)
    missing_findings = detect_missing_clauses(ctx)
    timings["benchmarking"] = (time.perf_counter() - t) * 1000

    t = stage("scoring", 92)
    findings = merge_findings(llm_findings + rule_findings + hidden_findings + bench_findings + missing_findings)
    mark_buried(ctx, findings)
    card = score_findings(ctx, findings)
    summary_provider = None if llm_stats and llm_stats.stopped_reason else provider
    summary, summary_source = build_summary(ctx, findings, benchmarks, card, summary_provider, redactor)
    timings["scoring"] = (time.perf_counter() - t) * 1000

    engine = EngineStats(
        mode="hybrid" if llm_stats and (llm_stats.reviewed_clauses or not llm_stats.batches) else "local",
        llm_provider=provider.name if provider else None,
        llm_model=(", ".join([provider.model] + sorted(provider.models_used - {provider.model}))
                   if provider else None),
        embedding_backend=embedder.backend,
        llm_batches=llm_stats.batches if llm_stats else 0,
        llm_failed_batches=llm_stats.failed_batches if llm_stats else 0,
        llm_findings_proposed=llm_stats.proposed if llm_stats else 0,
        llm_findings_rejected_unverified=llm_stats.rejected if llm_stats else 0,
        rule_findings=len(rule_findings) + len(hidden_findings) + len(bench_findings) + len(missing_findings),
        stage_timings_ms={k: round(v, 1) for k, v in timings.items()},
        warnings=warnings,
    )
    report("done", "Analysis complete", 100)
    return AnalysisResult(
        analysis_id=analysis_id,
        document_id=document_id,
        filename=filename,
        doc_type=playbook.id,
        doc_type_label=playbook.name,
        jurisdiction=jurisdiction,
        jurisdiction_label=JURISDICTION_LABELS.get(jurisdiction, jurisdiction),
        perspective=persp.id,
        perspective_label=persp.label,
        parties=parties,
        summary=summary,
        summary_source=summary_source,
        clauses=ctx.clauses,
        findings=findings,
        benchmarks=benchmarks,
        scorecard=card,
        engine=engine,
        playbook_version=playbook.version,
        prompt_version=PROMPT_VERSION,
        text_length=len(text),
        disclaimer=DISCLAIMER,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
