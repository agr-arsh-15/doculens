"""Recall check against ToS;DR (Terms of Service; Didn't Read, CC BY-SA) crowd-reviewed points.

For each service, approved points classified "bad" or "blocker" are mapped to DocuLens ToS clause
types by case title. The cited terms page is fetched, converted to text and analysed with the
ToS playbook from the user's perspective. A point counts as caught when DocuLens raises a risk
finding of the mapped clause type on that document. Points whose case has no DocuLens equivalent
are skipped, and the count of skipped cases is reported.

Needs internet access. Usage (from backend/):
    python -m eval.tosdr_eval                         # default services
    python -m eval.tosdr_eval --services 225 194 185  # ToS;DR service ids
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser

API = "https://api.tosdr.org/service/v3?id={id}"
DEFAULT_SERVICES = [158, 225, 194, 185, 270]  # Apple, Spotify, Reddit, Netflix, Dropbox
UA = {"User-Agent": "Mozilla/5.0 (DocuLens evaluation script)"}

CASE_RULES = [
    (r"terms (may|can) be changed|change (the|these) terms|without notice to you", {"modification"}),
    (r"arbitration|class action", {"arbitration"}),
    (r"(suspend|terminate|delete).{0,40}account|stop providing the service|terminate.{0,30}(at any time|for any reason)", {"account_termination"}),
    (r"tracked|tracking|fingerprint|personal data.{0,40}(sold|shared|advertis)|targeted advertising|third.party (cookies|advertisers)", {"data_privacy"}),
    (r"liabilit|not (be )?(responsible|liable)", {"liability"}),
    (r"(license|licence).{0,60}content|your content|content you post", {"user_content"}),
    (r"indemnif|defend", {"indemnify_provider"}),
    (r"renew|automatic(ally)? (charge|bill)|refund", {"billing"}),
]


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "br", "tr"}
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _get(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as resp:
        return resp.read()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n(\s*\n)+", "\n\n", text).strip()


def expected_types(case_title: str):
    for pattern, types in CASE_RULES:
        if re.search(pattern, case_title, re.I):
            return types
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--services", type=int, nargs="+", default=DEFAULT_SERVICES)
    p.add_argument("--tfidf", action="store_true", help="disable neural embeddings")
    p.add_argument("--json", metavar="PATH")
    args = p.parse_args()
    if args.tfidf:
        os.environ["DISABLE_NEURAL_EMBEDDINGS"] = "1"
    from eval.harness import analyze_bytes

    caught, total, skipped = 0, 0, 0
    by_type = defaultdict(lambda: [0, 0])
    misses, rows = [], []
    for sid in args.services:
        try:
            service = json.loads(_get(API.format(id=sid)))
        except Exception as exc:
            print(f"service {sid}: API error {exc}")
            continue
        docs = {str(d["id"]): d["url"] for d in service.get("documents", [])}
        points_by_url = defaultdict(list)
        for pt in service.get("points", []):
            case = pt.get("case") or {}
            if pt.get("status") != "approved" or case.get("classification") not in ("bad", "blocker"):
                continue
            types = expected_types(case.get("title", ""))
            if types is None:
                skipped += 1
                continue
            url = pt.get("source") or docs.get(str(pt.get("document_id")))
            if url:
                points_by_url[url].append((case["title"], types))

        for url, points in points_by_url.items():
            try:
                text = html_to_text(_get(url).decode("utf-8", "replace"))
            except Exception as exc:
                print(f"  {service['name']}: could not fetch {url} ({exc})")
                continue
            if len(text.split()) < 300:
                print(f"  {service['name']}: {url} has too little static text, skipped")
                continue
            run = analyze_bytes(text.encode("utf-8"), f"{service['name']}.txt", doc_type="tos", perspective="user")
            flagged = {f.clause_type for f in run.result.findings if not f.favorable and f.severity != "info"}
            for title, types in points:
                hit = bool(types & flagged)
                total += 1
                caught += hit
                for t in types:
                    by_type[t][0] += hit
                    by_type[t][1] += 1
                if not hit:
                    misses.append(f"{service['name']}: {title}")
            rows.append((service["name"], url, len(points), sum(bool(t & flagged) for _, t in points),
                         run.timings_ms["total"]))

    print(f"\n{'service':14} {'points':>6} {'caught':>6} {'ms':>6}  document")
    for name, url, n, hit, ms in rows:
        print(f"{name[:14]:14} {n:6} {hit:6} {ms:6.0f}  {url}")
    print(f"\n{'clause type':22} {'recall':>7} {'points':>6}")
    for t, (hit, n) in sorted(by_type.items()):
        print(f"{t:22} {hit / n:7.0%} {n:6}")
    recall = caught / total if total else 0.0
    print(f"\nrecall {caught}/{total} = {recall:.1%}   ({skipped} bad/blocker points have no DocuLens equivalent)")
    if misses:
        print("\nMissed:")
        for m in misses:
            print(f"  - {m}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"recall": recall, "caught": caught, "total": total, "skipped": skipped,
                       "by_type": {t: {"caught": h, "total": n} for t, (h, n) in by_type.items()}, "misses": misses}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
