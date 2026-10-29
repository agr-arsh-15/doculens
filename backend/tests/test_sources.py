"""Every market standard and benchmark range shown to users must be backed by a trusted, linkable source."""
from app.playbooks.loader import domain_allowed, load_playbooks, load_sources, url_host


def test_every_source_is_https_on_an_allowed_domain():
    registry = load_sources()
    for s in registry.sources:
        assert s.url.startswith("https://"), s.id
        assert domain_allowed(url_host(s.url), registry.allowed_domains[s.tier]), f"{s.id}: {s.url}"


def test_every_market_standard_has_a_source():
    missing = [f"{b.id}.{c.id}" for b in load_playbooks().values() for c in b.clauses
               if c.market_standard.strip() and not c.sources]
    assert not missing, f"Market standards without sources: {missing}"


def test_every_benchmark_range_has_a_source():
    missing = []
    for b in load_playbooks().values():
        for c in b.clauses:
            for m in c.metrics:
                if m.range is not None and not m.range.sources:
                    missing.append(f"{b.id}.{m.id} (default)")
                missing += [f"{b.id}.{m.id} ({j})" for j, r in m.jurisdictions.items() if not r.sources]
    assert not missing, f"Benchmark ranges without sources: {missing}"


def test_every_referenced_source_id_exists():
    known = load_sources().by_id()
    for b in load_playbooks().values():
        for c in b.clauses:
            ids = c.sources + c.references + [i for r in c.red_flags for i in r.sources]
            ids += [i for m in c.metrics for r in m.all_ranges() for i in r.sources]
            assert set(ids) <= set(known), f"{b.id}.{c.id}: {set(ids) - set(known)}"


def test_no_benchmark_without_a_sourced_range_for_the_jurisdiction():
    """A jurisdiction with no sourced range gets no market slider rather than an unsourced default."""
    from app.playbooks.loader import get_playbook

    metric = next(m for c in get_playbook("offer_letter").clauses for m in c.metrics if m.id == "notice_days")
    assert metric.range_for("SG") is None
    assert metric.range_for("IN").sources
