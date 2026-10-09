#!/usr/bin/env python
"""Run a fixed workload for hours and report whether it got slower.

The acceptance criterion the roadmap sets for issue #43 is "two hours continuous without
degradation", and there has never been a way to check it. #43 was closed by its reporter
in 2022 as a problem in their own application, so it is not an open lead -- but the
criterion is about this library's behaviour over time, and the project's own notes list
the audit of every ``release_jabelement`` path as unfinished work. Somebody has to be able
to measure the thing before saying it is done.

**What this measures is the symptom, not a diagnosis.** #43 reads "gets slower until it
stalls, with CPU and memory normal". A script can measure *getting slower*. It cannot
measure "a Java object leaked", because a leak is one cause among several -- a growing
tree, an accumulating log, a platform handle table -- and a rising latency curve does not
distinguish them. The report says which of the two it is showing.

What it does
------------

Attaches once, then repeatedly runs the same workload against the same window, recording
for each sample:

* how long the workload took, in milliseconds;
* the Java process's resident memory, via ``GetProcessMemoryInfo``.

Then it compares the first quarter of the samples with the last. Latency is noisy, so the
comparison is between medians rather than between endpoints: a single slow sample at
minute 3 must not decide the answer.

Reading the output
------------------

**A ratio near 1.0 is the result you want and is not a proof of anything.** Two hours is
long enough to catch a leak that costs a few milliseconds a minute and far too short to
catch one that costs a byte a lookup. The thresholds are conventional, not derived:
1.25x is flagged as a trend, 2.0x as degradation. Say what was measured rather than
letting a green line imply more.

Usage
-----

    java -cp tests/java/classes PyjabTestApp --title "PyjabTestApp"
    python tools/soak.py --title PyjabTestApp --minutes 120

`--minutes 1` is a smoke run: it checks the harness works rather than the library.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: The workload. Chosen to exercise the traversals rather than one fast path: an absolute
#: xpath (which takes the top-level object), a relative one, a name lookup, and an
#: enumeration. Every one of these creates references, which is the thing under test.
WORKLOAD = [
    "find_element_by_xpath", "//push button",
    "find_element_by_xpath", ".//label",
    "find_element_by_name", "OK",
    "find_elements_by_xpath", "//label",
    "get_children", None,
]

#: Where the report changes its mind. Conventional, and stated as such in the output.
TREND_RATIO = 1.25
DEGRADED_RATIO = 2.00


def run_workload(driver) -> None:
    """One pass of WORKLOAD against an attached driver.

    Failures are not caught: a workload that stopped working part way through would
    otherwise show up as a *faster* run, which is the one wrong answer that looks like a
    good one.
    """
    from pyjab.common.exceptions import JABException

    for index in range(0, len(WORKLOAD), 2):
        method, value = WORKLOAD[index], WORKLOAD[index + 1]
        try:
            if method == "get_children":
                found = driver.root_element.get_children()
            else:
                found = getattr(driver, method)(value)
        except JABException:
            # An ordinary miss on a window that has no such control is not a failure of
            # the soak; it still did the work of looking.
            continue
        for element in (found if isinstance(found, list) else [found]):
            if element is not None and element is not driver.root_element:
                element.release_jabelement()


def memory_of(pid: int) -> int:
    """The Java process's resident bytes, or 0 if it could not be read.

    Read through pywin32 rather than psutil: pywin32 is already a runtime dependency and
    psutil would be a new one for a maintainer script.
    """
    try:
        import win32api
        import win32con
        import win32process

        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        try:
            return win32process.GetProcessMemoryInfo(handle)["WorkingSetSize"]
        finally:
            win32api.CloseHandle(handle)
    except Exception:                            # noqa: BLE001 - reported as 0
        return 0


# ---------------------------------------------------------------------------
# Analysis -- pure, and therefore testable anywhere
# ---------------------------------------------------------------------------

def quarters(values: list) -> tuple:
    """The first and last quarter of a series, medians taken.

    Medians rather than endpoints because latency is noisy: one slow sample at minute
    three, or one fast one at the end, would otherwise decide the answer by itself.
    """
    if len(values) < 4:
        return None, None
    size = max(1, len(values) // 4)
    return statistics.median(values[:size]), statistics.median(values[-size:])


def slope_per_hour(values: list, seconds_per_sample: float) -> float:
    """Least-squares slope of the series, in units per hour.

    Reported alongside the ratio because the two answer different questions: the ratio
    says how much worse it ended up, the slope says how steadily. A leak that costs a
    fixed amount per iteration shows a flat-ish ratio early and a large slope.
    """
    if len(values) < 4 or seconds_per_sample <= 0:
        return 0.0
    n = len(values)
    xs = [i * seconds_per_sample / 3600.0 for i in range(n)]
    mean_x, mean_y = statistics.mean(xs), statistics.mean(values)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denominator


def verdict(latencies: list, seconds_per_sample: float) -> dict:
    """What the samples say, and what they do not.

    Deliberately returns the numbers it judged on, so the report can show them rather
    than asking a reader to trust a word.
    """
    first, last = quarters(latencies)
    if first is None:
        return {"outcome": "too few samples",
                "detail": f"{len(latencies)} sample(s); four are needed to compare "
                          "a first and a last quarter"}
    if first == 0:
        return {"outcome": "unusable",
                "detail": "the first quarter's median latency was 0 ms"}

    ratio = last / first
    result = {
        "first_quarter_median_ms": round(first, 2),
        "last_quarter_median_ms": round(last, 2),
        "ratio": round(ratio, 3),
        "slope_ms_per_hour": round(slope_per_hour(latencies, seconds_per_sample), 2),
        "samples": len(latencies),
    }
    if ratio >= DEGRADED_RATIO:
        result["outcome"] = "DEGRADED"
        result["detail"] = (
            f"the last quarter took {ratio:.2f}x the first. That is the symptom #43 "
            "describes. It is not by itself evidence of a leaked Java object -- see the "
            "note at the top of this file -- so treat it as a reason to look, with the "
            "reference counts in tools/check_jab_object_sites.py as one place to start."
        )
    elif ratio >= TREND_RATIO:
        result["outcome"] = "TREND"
        result["detail"] = (
            f"the last quarter took {ratio:.2f}x the first, which is above the "
            f"{TREND_RATIO}x this script flags. Not conclusive: latency drifts with "
            "machine load as well. Run it again on a quiet machine before believing it."
        )
    else:
        result["outcome"] = "STABLE"
        result["detail"] = (
            f"the last quarter took {ratio:.2f}x the first, inside the {TREND_RATIO}x "
            "this script treats as drift. **This is not a proof that nothing leaks.** A "
            "run this long catches a leak costing milliseconds a minute, not one costing "
            "a byte a lookup."
        )
    return result



# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--title", required=True)
    parser.add_argument("--minutes", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=60.0,
                        help="seconds of work between samples (default 60)")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("A soak run needs Windows: pyjab drives the Java Access Bridge.",
              file=sys.stderr)
        return 2

    from pyjab.jabdriver import JABDriver

    # Attached, not launched, so no __exit__: that terminates the bound process by pid,
    # which is right for a driver that started one and wrong here.
    driver = JABDriver(title=args.title, timeout=args.timeout)
    pid = driver.pid
    deadline = time.monotonic() + args.minutes * 60
    latencies, memories, stamps = [], [], []

    print(f"soaking {args.title!r} for {args.minutes:g} minute(s), "
          f"pid {pid}, {args.interval:g}s between samples\n")
    started = time.monotonic()
    try:
        while time.monotonic() < deadline:
            sample_started = time.monotonic()
            run_workload(driver)
            elapsed = (time.monotonic() - sample_started) * 1000.0

            latencies.append(elapsed)
            memories.append(memory_of(pid))
            stamps.append(time.monotonic() - started)

            print(f"  t={stamps[-1]:7.1f}s  latency={elapsed:8.2f}ms  "
                  f"rss={memories[-1] / 1048576:7.1f}MB  n={len(latencies)}")
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(args.interval, remaining))
    except KeyboardInterrupt:
        print("\nstopped early; reporting what was collected")

    if not latencies:
        print("no samples were collected", file=sys.stderr)
        return 1

    span = stamps[-1] - stamps[0]
    per_sample = (span / (len(latencies) - 1)) if len(latencies) > 1 else args.interval
    result = verdict(latencies, per_sample)

    first_mem, last_mem = quarters(memories)
    memory_note = "unavailable"
    if first_mem is not None:
        memory_note = (f"{first_mem / 1048576:.1f}MB -> {last_mem / 1048576:.1f}MB "
                       f"({last_mem / first_mem:.2f}x)" if first_mem else "unavailable")

    if args.json:
        print(json.dumps({"title": args.title, "minutes": args.minutes,
                          "latency": result, "memory": memory_note,
                          "samples": len(latencies)}, indent=2, ensure_ascii=False))
    else:
        print(f"\n  {len(latencies)} samples over {span / 60:.1f} minutes "
              f"({per_sample:.1f}s apart)")
        print(f"  latency:  {result.get('first_quarter_median_ms')}ms -> "
              f"{result.get('last_quarter_median_ms')}ms  "
              f"ratio {result.get('ratio')}  slope "
              f"{result.get('slope_ms_per_hour')}ms/hour")
        print(f"  memory:   {memory_note}")
        print(f"\n  {result['outcome']}: {result['detail']}\n")

    return 0 if result["outcome"] in ("STABLE", "TREND", "too few samples") else 1


if __name__ == "__main__":
    sys.exit(main())
