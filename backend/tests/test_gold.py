"""Regression gate over the hand-labeled sample set (tests/fixtures/gold). See eval/run_eval.py for metrics."""
import pytest

from eval.gold import all_gold, score_run
from eval.harness import analyze_sample

GOLD = all_gold()


@pytest.fixture(scope="module", params=GOLD, ids=[g.sample for g in GOLD])
def scored(request):
    gold = request.param
    run = analyze_sample(gold.sample, use_llm=False)
    return score_run(gold, run.detection, run.result, run.timings_ms, run.text)


def test_detection(scored):
    assert scored.detection_ok, scored.detection_note


def test_required_findings_are_raised(scored):
    assert not scored.missed


def test_severity_meets_labels(scored):
    assert not scored.severity_misses


def test_no_known_false_positives(scored):
    assert not scored.forbidden_hits


def test_no_unlabeled_findings(scored):
    assert not scored.false_positives


def test_benchmarks_extracted(scored):
    assert not scored.benchmark_misses


def test_score_in_expected_band(scored):
    assert scored.score_ok, scored.score


def test_every_quote_is_verbatim(scored):
    assert scored.quotes_unverifiable == 0
