"""Clause-mapping evaluation on CUAD (Contract Understanding Atticus Dataset, CC BY 4.0).

CUAD has 510 commercial contracts in which lawyers annotated 41 clause categories. This script
segments each test contract with DocuLens, maps clauses with the MSA/SaaS playbook, and checks
the mapping against the CUAD categories that correspond to DocuLens clause types:

  - document level: does DocuLens find the clause type exactly when CUAD says the contract has it?
  - span level:     is each annotated CUAD span inside a clause that DocuLens gave that type?

Usage (from backend/):
    python -m eval.cuad_eval --download          # fetch CUAD data.zip (~18 MB) into eval/.cache
    python -m eval.cuad_eval --limit 40 [--tfidf] [--json out.json]
"""
import argparse
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

CUAD_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
CACHE = Path(__file__).resolve().parent / ".cache"

# CUAD "Audit Rights" (either party audits books) and "Warranty Duration" (a warranty period) are
# not mapped: they do not mean the same thing as DocuLens' vendor-audit and as-is disclaimer types.
# "termination" is broader than CUAD's "Termination For Convenience", so its doc precision is a floor.
CATEGORY_MAP = {
    "Cap On Liability": "liability_cap",
    "Termination For Convenience": "termination",
    "Renewal Term": "term_renewal",
    "Notice Period To Terminate Renewal": "term_renewal",
    "Governing Law": "governing_law",
    "Ip Ownership Assignment": "ip_ownership",
}


def download() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / "test.json"
    if target.exists():
        return target
    print(f"Downloading {CUAD_URL} ...")
    with urllib.request.urlopen(CUAD_URL, timeout=120) as resp:
        archive = zipfile.ZipFile(io.BytesIO(resp.read()))
    name = next(n for n in archive.namelist() if n.endswith("test.json"))
    target.write_bytes(archive.read(name))
    print(f"Saved {target}")
    return target


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def load_contracts(path: Path, limit: int):
    data = json.loads(path.read_text())["data"]
    for entry in data[:limit]:
        para = entry["paragraphs"][0]
        gold = defaultdict(list)
        for qa in para["qas"]:
            category = qa["id"].split("__")[-1]
            if category in CATEGORY_MAP:
                gold[CATEGORY_MAP[category]] += [a["text"] for a in qa["answers"] if a["text"].strip()]
        yield entry["title"], para["context"], gold


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--download", action="store_true", help="download CUAD into eval/.cache")
    p.add_argument("--data", type=Path, default=CACHE / "test.json", help="path to CUAD test.json (SQuAD format)")
    p.add_argument("--limit", type=int, default=40, help="number of contracts to evaluate")
    p.add_argument("--tfidf", action="store_true", help="disable neural embeddings")
    p.add_argument("--json", metavar="PATH", help="write per-type metrics as JSON")
    args = p.parse_args()
    if args.tfidf:
        os.environ["DISABLE_NEURAL_EMBEDDINGS"] = "1"
    if args.download:
        args.data = download()
    if not args.data.exists():
        print(f"{args.data} not found. Run with --download first.", file=sys.stderr)
        return 2

    from app.analysis.context import AnalysisContext
    from app.analysis.mapping import map_clauses
    from app.ingestion.parser import parse_document
    from app.playbooks.loader import get_playbook
    from app.structure.segmenter import segment_document

    playbook = get_playbook("msa_saas")
    types = sorted(set(CATEGORY_MAP.values()))
    doc = {t: {"tp": 0, "fp": 0, "fn": 0} for t in types}
    span = {t: {"hit": 0, "total": 0} for t in types}
    n = 0
    for title, context, gold in load_contracts(args.data, args.limit):
        parsed = parse_document(context.encode("utf-8"), f"{title[:40]}.txt")
        clauses = segment_document(parsed.text, parsed.pages, parsed.heading_hints)
        ctx = AnalysisContext(text=parsed.text, clauses=clauses, playbook=playbook,
                              perspective=playbook.perspective(None), jurisdiction="US")
        map_clauses(ctx)
        n += 1
        for t in types:
            predicted = ctx.clauses_of_type(t)
            present = bool(gold.get(t))
            if predicted and present:
                doc[t]["tp"] += 1
            elif predicted:
                doc[t]["fp"] += 1
            elif present:
                doc[t]["fn"] += 1
            typed_text = [_norm(c.text) for c in predicted]
            for answer in gold.get(t, []):
                span[t]["total"] += 1
                needle = _norm(answer)[:200]
                if any(needle in body for body in typed_text):
                    span[t]["hit"] += 1

    print(f"CUAD clause mapping on {n} contracts (MSA/SaaS playbook)\n")
    print(f"{'clause type':22} {'doc P':>6} {'doc R':>6} {'doc F1':>7} {'span R':>7} {'spans':>6}")
    report = {}
    for t in types:
        tp, fp, fn = doc[t]["tp"], doc[t]["fp"], doc[t]["fn"]
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        srec = span[t]["hit"] / span[t]["total"] if span[t]["total"] else 0.0
        report[t] = {"doc_precision": prec, "doc_recall": rec, "doc_f1": f1, "span_recall": srec, "spans": span[t]["total"]}
        print(f"{t:22} {prec:6.0%} {rec:6.0%} {f1:7.0%} {srec:7.0%} {span[t]['total']:6}")
    macro_f1 = sum(r["doc_f1"] for r in report.values()) / len(report)
    total_spans = sum(s["total"] for s in span.values())
    micro_span = sum(s["hit"] for s in span.values()) / total_spans if total_spans else 0.0
    print(f"\nmacro doc F1 {macro_f1:.1%}   micro span recall {micro_span:.1%}")
    if args.json:
        Path(args.json).write_text(json.dumps({"contracts": n, "types": report, "macro_doc_f1": macro_f1,
                                               "micro_span_recall": micro_span}, indent=2))
        print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
