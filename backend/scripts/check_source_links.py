"""Check that every source URL in the registry still resolves.

Usage (from backend/):  ../.venv/bin/python scripts/check_source_links.py [--report out.md]

Exit code 1 when a link is definitely broken (404/410 from a host without bot protection).
Hosts listed under bot_protected in sources.yaml often answer scripts with 403/404/202, so problems
there are reported as warnings to check by hand instead of failures.
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.playbooks.loader import domain_allowed, load_sources, url_host  # noqa: E402

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/pdf,*/*;q=0.8",
}


def _check(url: str):
    try:
        with httpx.Client(follow_redirects=True, timeout=25, headers=_HEADERS) as client:
            r = client.get(url)
            return r.status_code, None
    except httpx.HTTPError as exc:
        return None, type(exc).__name__


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="Write a Markdown report to this path")
    args = parser.parse_args()

    registry = load_sources()
    by_url = {}
    for s in registry.sources:
        by_url.setdefault(s.url, []).append(s.id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(by_url, pool.map(_check, by_url)))

    broken, warnings = [], []
    for url, (status, error) in results.items():
        ids = ", ".join(by_url[url])
        protected = domain_allowed(url_host(url), registry.bot_protected)
        if status is not None and status < 400:
            continue
        line = f"- `{ids}` {url} -> {status or error}"
        if not protected and status in (404, 410):
            broken.append(line)
        else:
            warnings.append(line)

    lines = [f"Checked {len(results)} source URLs: {len(broken)} broken, {len(warnings)} to check by hand."]
    if broken:
        lines += ["", "## Broken", *broken]
    if warnings:
        lines += ["", "## Check by hand (bot protection, timeouts or server errors)", *warnings]
    report = "\n".join(lines)
    print(report)
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
