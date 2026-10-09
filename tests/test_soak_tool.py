"""The soak run's analysis, which is the part that can be checked without Windows.

The measurement needs a Java application and two hours; the arithmetic does not. What
matters about the arithmetic is that it says what it measured and does not claim more:
"the last quarter took 1.03x the first" is a fact, and "nothing leaks" is not.

The thresholds are conventional. These tests pin the behaviour rather than the numbers,
so that changing a threshold is a deliberate edit rather than a test that quietly follows
it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    spec = importlib.util.spec_from_file_location(
        "soak", REPO_ROOT / "tools" / "soak.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["soak"] = module
    spec.loader.exec_module(module)
    return module


soak = load()


def without_noise(values):
    """A series with a little jitter, so medians have something to be robust about."""
    return [value + (2 if index % 2 else -2) for index, value in enumerate(values)]


# ---------------------------------------------------------------------------
# Quarters, because latency is noisy
# ---------------------------------------------------------------------------

def test_quarters_take_medians_of_the_ends():
    first, last = soak.quarters([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    assert first == pytest.approx(1.5)
    assert last == pytest.approx(7.5)


def test_one_slow_sample_does_not_decide_the_answer():
    """The reason for medians rather than endpoints.

    A single hiccup at minute three -- another process starting, a GC pause -- must not
    be able to make a steady run look degraded.
    """
    steady = without_noise([100.0] * 40)
    with_one_spike = list(steady)
    with_one_spike[1] = 9000.0

    assert soak.verdict(steady, 60.0)["outcome"] == "STABLE"
    assert soak.verdict(with_one_spike, 60.0)["outcome"] == "STABLE"


def test_too_few_samples_is_said_rather_than_guessed():
    result = soak.verdict([100.0, 101.0], 60.0)
    assert result["outcome"] == "too few samples"
    assert "four" in result["detail"]


# ---------------------------------------------------------------------------
# The three outcomes
# ---------------------------------------------------------------------------

def test_a_flat_run_is_stable():
    result = soak.verdict(without_noise([100.0] * 40), 60.0)
    assert result["outcome"] == "STABLE"
    assert result["ratio"] == pytest.approx(1.0, abs=0.05)


def test_a_steady_climb_is_a_trend_not_a_verdict():
    """Between the thresholds it asks for a second run rather than concluding."""
    result = soak.verdict([100.0 + index for index in range(40)], 60.0)
    assert result["outcome"] == "TREND"
    assert "Run it again" in result["detail"]


def test_a_runaway_climb_is_degraded():
    result = soak.verdict([100.0 * (1.1 ** index) for index in range(40)], 60.0)
    assert result["outcome"] == "DEGRADED"
    assert result["ratio"] > soak.DEGRADED_RATIO


def test_a_stable_result_does_not_claim_there_is_no_leak():
    """The sentence that matters most in this file.

    Two hours catches a leak costing milliseconds a minute and not one costing a byte a
    lookup. A green line must not be allowed to imply the stronger claim.
    """
    detail = soak.verdict(without_noise([100.0] * 40), 60.0)["detail"]

    assert "not a proof" in detail
    assert "byte a lookup" in detail


def test_a_degraded_result_does_not_claim_a_leak_was_found():
    """The other half: a rising curve is a symptom, and #43 lists more than one cause."""
    detail = soak.verdict([100.0 * (1.1 ** index) for index in range(40)], 60.0)["detail"]

    assert "not by itself evidence" in detail
    assert "reason to look" in detail


# ---------------------------------------------------------------------------
# The slope, which answers a different question from the ratio
# ---------------------------------------------------------------------------

def test_the_slope_is_in_milliseconds_per_hour():
    """One millisecond more per sample, a minute apart, is 60 ms an hour."""
    series = [100.0 + index for index in range(60)]
    assert soak.slope_per_hour(series, 60.0) == pytest.approx(60.0, rel=0.01)


def test_a_flat_series_has_no_slope():
    assert soak.slope_per_hour([100.0] * 40, 60.0) == pytest.approx(0.0, abs=1e-9)


def test_a_series_too_short_for_a_slope_reports_zero_rather_than_raising():
    assert soak.slope_per_hour([100.0], 60.0) == 0.0
    assert soak.slope_per_hour([], 60.0) == 0.0


def test_a_zero_interval_does_not_divide_by_zero():
    assert soak.slope_per_hour([100.0, 200.0, 300.0, 400.0], 0.0) == 0.0


def test_a_zero_first_quarter_is_reported_as_unusable():
    """Rather than as an infinite ratio."""
    result = soak.verdict([0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0], 60.0)
    assert result["outcome"] == "unusable"


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------

def test_the_workload_pairs_every_method_with_an_argument():
    assert len(soak.WORKLOAD) % 2 == 0


def test_the_workload_exercises_more_than_one_traversal():
    """A soak that hammers one fast path measures that fast path."""
    methods = soak.WORKLOAD[0::2]
    assert len(set(methods)) >= 3, methods


def test_it_refuses_to_run_off_windows(capsys, monkeypatch):
    """The platform is forced rather than assumed.

    The first version of this test did not force it, so it passed on macOS and Linux and
    failed on Windows -- where ``main()`` went on to attach to a window that does not
    exist. A test about the non-Windows path has to say which platform it is testing.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "argv", ["soak.py", "--title", "X", "--minutes", "0.1"])

    assert soak.main() == 2
    assert "needs Windows" in capsys.readouterr().err
