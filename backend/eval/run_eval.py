"""Evaluate the DocuLens pipeline against the hand-labeled gold set.

Usage (from backend/):
    python -m eval.run_eval                 # local mode, neural embeddings if available
    python -m eval.run_eval --tfidf         # force the TF-IDF fallback
    python -m eval.run_eval --llm           # hybrid mode (needs an LLM key in .env)
    python -m eval.run_eval --json out.json --strict

Reports per-sample and micro-averaged precision/recall over risk findings, severity agreement,
forbidden false positives, benchmark extraction accuracy, unverifiable-quote rate and timings.
"""
import argparse
import json
import os
import statistics
import sys
from dataclasses import asdict


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", action="store_true", help="enable LLM clause reasoning (hybrid mode)")
    p.add_argument("--tfidf", action="store_true", help="disable neural embeddings")
    p.add_argument("--json", metavar="PATH", help="write the full report as JSON")
    p.add_argument("--strict", action="store_true", help="exit 1 on any missed, forbidden or benchmark error")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.tfidf:
        os.environ["DISABLE_NEURAL_EMBEDDINGS"] = "1"

    from eval.gold import all_gold, score_run
    from eval.harness import analyze_sample

    scores = []
    for gold in all_gold():
        run = analyze_sample(gold.sample, use_llm=args.llm)
        scores.append(score_run(gold, run.detection, run.result, run.timings_ms, run.text))
        mode = run.result.engine.mode

    header = f"{'sample':26} {'detect':6} {'recall':>7} {'prec':>6} {'FP':>3} {'forbid':>6} {'bench':>5} {'sev':>3} {'quotes':>7} {'score':>5} {'ms':>6}"
    print(f"DocuLens eval  mode={mode}  embeddings={'tfidf' if args.tfidf else 'default'}\n")
    print(header)
    print("-" * len(header))
    for s in scores:
        recall = s.recall_hits / s.required_total if s.required_total else 1.0
        precision = s.true_positives / s.flagged if s.flagged else 1.0
        print(f"{s.sample[:26]:26} {'ok' if s.detection_ok else 'FAIL':6} {recall:7.0%} {precision:6.0%} "
              f"{len(s.false_positives):3} {len(s.forbidden_hits):6} {len(s.benchmark_misses):5} {len(s.severity_misses):3} "
              f"{s.quotes_unverifiable:>3}/{s.quotes_total:<3} {s.score:5} {s.timings_ms.get('total', 0):6.0f}")

    tp = sum(s.true_positives for s in scores)
    flagged = sum(s.flagged for s in scores)
    req = sum(s.required_total for s in scores)
    hit = sum(s.recall_hits for s in scores)
    quotes = sum(s.quotes_total for s in scores)
    unver = sum(s.quotes_unverifiable for s in scores)
    totals = [s.timings_ms.get("total", 0) for s in scores]
    summary = {
        "mode": mode,
        "micro_precision": tp / flagged if flagged else 1.0,
        "micro_recall": hit / req if req else 1.0,
        "detection_accuracy": sum(s.detection_ok for s in scores) / len(scores),
        "unverifiable_quote_rate": unver / quotes if quotes else 0.0,
        "forbidden_hits": sum(len(s.forbidden_hits) for s in scores),
        "benchmark_errors": sum(len(s.benchmark_misses) for s in scores),
        "severity_disagreements": sum(len(s.severity_misses) for s in scores),
        "median_ms": statistics.median(totals),
        "max_ms": max(totals),
    }
    print("-" * len(header))
    print(f"micro precision {summary['micro_precision']:.1%}   micro recall {summary['micro_recall']:.1%}   "
          f"detection {summary['detection_accuracy']:.0%}   unverifiable quotes {summary['unverifiable_quote_rate']:.1%}")
    print(f"timing median {summary['median_ms']:.0f} ms, max {summary['max_ms']:.0f} ms")

    problems = []
    for s in scores:
        for label in s.missed:
            problems.append(f"{s.sample}: missed required '{label}'")
        problems += [f"{s.sample}: severity {m}" for m in s.severity_misses]
        problems += [f"{s.sample}: forbidden {m}" for m in s.forbidden_hits]
        problems += [f"{s.sample}: benchmark {m}" for m in s.benchmark_misses]
        problems += [f"{s.sample}: unlabeled finding {m}" for m in s.false_positives]
        if not s.detection_ok:
            problems.append(f"{s.sample}: {s.detection_note}")
        if not s.score_ok:
            problems.append(f"{s.sample}: score {s.score} outside expected range")
    if problems:
        print("\nIssues:")
        for p in problems:
            print(f"  - {p}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"summary": summary, "samples": [asdict(s) for s in scores]}, fh, indent=2)
        print(f"\nWrote {args.json}")

    hard_fail = any(s.missed or s.forbidden_hits or s.benchmark_misses or not s.detection_ok for s in scores)
    return 1 if args.strict and hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
