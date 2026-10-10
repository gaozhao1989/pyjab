#!/usr/bin/env python
"""M0: does JAB actually see more than UIA on a real Java application?

This is the go/no-go for the pyjab-mcp plan (`docs/PYJAB_MCP_PLAN.md` section 2.3). The
assumption behind the whole second layer is that pyjab's direct Java Access Bridge
connection is **clearly better** than reading the same application through UIA, which is
what a generic Windows automation server does. Nothing has ever tested it.

Why it is worth testing before writing any MCP code
--------------------------------------------------

If the answer is "about the same", the differentiation is gone and pyjab-mcp becomes one
optional backend among several rather than a product. If UIA is better, the direction
should be dropped. Either answer costs a few hours now and would cost months to
discover later.

What this measures, and what it does not
---------------------------------------

It measures the **accessibility tree**, not any particular client. UIA is read here with
a Python UIA client, not with FlaUI-MCP. That is a fair comparison of *semantics* --
FlaUI reads the same tree through the same `UIAutomationCore` API, and the tree is the
tree -- but it is **not** a measurement of FlaUI-MCP's own rendering, token budget or
tool design. Those are separate questions and this script does not answer them.

The distinction that matters most
---------------------------------

A comparison script that fails to read UIA would report "JAB sees 40 elements, UIA sees
0" and look like a decisive win for JAB. So every UIA reading here is a **status**, and
there are three of them, not two:

* a **count** -- what was measured;
* an :class:`Absent` -- the measurement *was* taken and the answer is "nothing there".
  UIA exposing no table is an answer, and it is the plan's own clear-win row: pyjab
  reads a table cell and UIA reports none;
* an :class:`Unavailable` -- the measurement could **not** be taken; the client is
  missing or the call failed. This is the one that is never rendered as a zero.

The report says which of the three each row is. Only the third makes the run
INCONCLUSIVE; treating the second as the third is what made the plan's clear-win row
unreachable, which is why ``Absent`` exists rather than a flag on ``Unavailable``.

Usage
-----

    pip install uiautomation          # the UIA side; JAB needs pyjab on Windows
    java -cp tests/java/classes PyjabTestApp --title=PyjabTestApp
    python tools/verify_m0.py --title PyjabTestApp

Add `--json` for a machine-readable report. Exit status is 0 if every measurement was
taken -- including the ones that found nothing -- and 1 if any could not be taken, so a
comparison that could not be made cannot look like a comparison that was.

Run it once per target the plan names: a JDK 8 login form, a JDK 17 window with a large
table, and a window with a tree, tabs and a dialog.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: What the plan asks each side to be able to do. Kept as data so the report and the
#: JSON say the same thing.
QUESTIONS = [
    ("windows", "enumerate top-level windows"),
    ("elements", "how many elements the tree exposes"),
    ("roles", "how many distinct roles"),
    ("named", "how many elements carry a non-empty name"),
    ("table", "find a table and report its size"),
    ("cell", "read one table cell's text"),
    ("tree", "find tree nodes and their text"),
    ("button", "find a button and read its role and states"),
    ("depth", "deepest level reached"),
]


class Unavailable:
    """A measurement that could not be taken, and why.

    Distinct from a measurement of zero on purpose. Rendering "could not read UIA" as
    "UIA has nothing" is the one way this script could produce a confidently wrong
    answer, and it is the answer that would most flatter the thing being tested.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail

    def __repr__(self) -> str:
        return f"unavailable: {self.reason}"


class Absent(Unavailable):
    """The measurement *was* taken, and the answer is: nothing there.

    This distinction is the whole point of the script. "UIA exposes no table" is an
    answer, and it is the plan's own clear-win row -- pyjab reads a table cell's text
    and UIA reports none. "UIA could not be enumerated" is not an answer, and reading
    it as one would flatter pyjab.

    Both used to be a plain ``Unavailable``, and ``report()`` judged them by their
    rendered string, so *every* absence made the run INCONCLUSIVE. That put
    ``verdict()``'s clear-win branch out of reach for the one case it was written
    for: when UIA finds no table it never sets ``cell`` at all, so the row counted as
    unanswered and the verdict returned before comparing anything.
    """

    def __repr__(self) -> str:
        return f"absent: {self.reason}"


def jab_side(title: str, timeout: int) -> dict:
    """Read the window through pyjab. Raises if pyjab cannot attach."""
    from pyjab.jabdriver import JABDriver
    from pyjab.inspector import bridge_without_window, walk
    from pyjab.common.win32utils import Win32Utils

    bridge = bridge_without_window()
    java_windows = [t for hwnd, t in Win32Utils().enum_windows().items()
                    if t and bridge.isJavaWindow(hwnd)]

    driver = JABDriver(title=title, timeout=timeout)
    # Not a context manager: __exit__ terminates the bound process by pid, and this
    # script attaches to an application it did not start.
    root = driver.root_element

    elements = [item for _depth, item in walk(root, None, None)]
    result = {
        "windows": {"java": len(java_windows), "sample": java_windows[:3]},
        "elements": len(elements),
        "roles": len({item["role"] for item in elements}),
        "named": sum(1 for item in elements if item["name"]),
        "depth": max((item["object_depth"] for item in elements), default=0),
        "role_counts": _counts(item["role"] for item in elements),
    }

    tables = [item for item in elements if "table" in item["role"]]
    if tables:
        result["table"] = {"role": tables[0]["role"], "name": tables[0]["name"],
                           "children": tables[0]["children_count"]}
        result["cell"] = _jab_cell(driver, root, tables[0])
    else:
        result["table"] = Absent("no element with 'table' in its role")
        # Explicit, because the completeness check looks at every question and this
        # one would otherwise fall back to report()'s "not measured" default -- which
        # means a *failure* to measure, and would keep the run INCONCLUSIVE even
        # though "there is no table" is a perfectly good answer.
        result["cell"] = Absent("no table, so no cell to read")

    nodes = [item for item in elements if "tree" in item["role"] or "list item" in item["role"]]
    result["tree"] = ({"count": len(nodes),
                       "named": sum(1 for item in nodes if item["name"]),
                       "sample": [item["name"] for item in nodes if item["name"]][:5]}
                      if nodes else Absent("no element with 'tree' in its role"))

    buttons = [item for item in elements if "push button" in item["role"]]
    result["button"] = ({"count": len(buttons),
                         "sample": buttons[0]["role"],
                         "states": buttons[0]["states"] or "(none reported)"}
                        if buttons else Absent("no push button found"))
    return result


def _jab_cell(driver, root, table_info) -> object:
    """The text of one table cell, via the table element's own children."""
    from pyjab.common.exceptions import JABException

    try:
        table = driver.root_element.find_element_by_role(table_info["role"])
    except JABException as exc:
        return Unavailable("could not bind the table again", str(exc))
    try:
        cells = table.get_children()
    except JABException as exc:
        return Unavailable("could not read the table's children", str(exc))
    if not cells:
        return Absent("the table reported no children")
    # Row-major as Swing reports it; index 6 is row 3, column 2 of a 3-wide table.
    index = min(6, len(cells) - 1)
    return {"index": index, "role": cells[index].role_en_us,
            "text": cells[index].name or "", "of": len(cells)}


def uia_side(title: str, timeout: int) -> dict:
    """Read the same window through UIA. Never raises; reports Unavailable instead."""
    try:
        import uiautomation
    except Exception as exc:                    # noqa: BLE001 - reported, not handled
        return {"_client": Unavailable("the uiautomation package is not importable",
                                       str(exc))}

    try:
        window = uiautomation.WindowControl(searchDepth=2, SubName=title,
                                            Timeout=timeout * 1000)
        if not window.Exists(maxSearchSeconds=timeout):
            return {"_client": Unavailable(f"no UIA window whose name contains {title!r}")}
    except Exception as exc:                    # noqa: BLE001
        return {"_client": Unavailable("attaching through UIA failed", str(exc))}

    result = {}
    try:
        top_level = [child for child in uiautomation.GetRootControl().GetChildren()
                     if child.ControlTypeName]
        result["windows"] = {"top_level": len(top_level),
                             "sample": [w.Name for w in top_level if w.Name][:3]}
    except Exception as exc:                    # noqa: BLE001
        result["windows"] = Unavailable("could not enumerate UIA windows", str(exc))

    try:
        elements = _uia_walk(window, 0)
    except Exception as exc:                    # noqa: BLE001
        return {"_client": Unavailable("walking the UIA tree failed", str(exc))}

    result["elements"] = len(elements)
    result["roles"] = len({item["role"] for item in elements})
    result["named"] = sum(1 for item in elements if item["name"])
    result["depth"] = max((item["depth"] for item in elements), default=0)
    result["role_counts"] = _counts(item["role"] for item in elements)

    tables = [item for item in elements if "table" in item["role"].lower()]
    if tables:
        result["table"] = {"role": tables[0]["role"], "name": tables[0]["name"]}
        result["cell"] = _uia_cell(tables[0])
    else:
        result["table"] = Absent("no UIA element with 'table' in its type")
        # Same reason as the JAB side: without this the row falls back to
        # report()'s "not measured" default, which is a failure to measure, and the
        # run stays INCONCLUSIVE even though "UIA has no table" is the answer.
        result["cell"] = Absent("no UIA table, so no cell to read")

    nodes = [item for item in elements
             if "tree" in item["role"].lower() or "listitem" in item["role"].lower()]
    result["tree"] = ({"count": len(nodes),
                       "named": sum(1 for item in nodes if item["name"]),
                       "sample": [item["name"] for item in nodes if item["name"]][:5]}
                      if nodes else Absent("no UIA element with 'tree' in its type"))

    buttons = [item for item in elements
               if "button" in item["role"].lower() and "listitem" not in item["role"].lower()]
    result["button"] = ({"count": len(buttons), "sample": buttons[0]["role"],
                         "states": buttons[0].get("patterns", "(not read)")}
                        if buttons else Absent("no UIA button found"))
    return result


def _uia_walk(control, depth, limit=4000):
    """A flat list of what UIA exposes, for comparison with ``inspector.walk``.

    Depth-limited and counted, because a UIA tree can be enormous and this is a
    measurement rather than a dump.
    """
    collected = []
    if depth > 30 or len(collected) > limit:
        return collected
    try:
        children = control.GetChildren()
    except Exception:                           # noqa: BLE001
        return collected
    for child in children:
        try:
            role = child.ControlTypeName
            name = child.Name or ""
            patterns = ",".join(sorted(
                p.split("Pattern")[0].lower()
                for p in getattr(child, "GetSupportedPatterns", lambda: [])()
            )) if hasattr(child, "GetSupportedPatterns") else ""
        except Exception:                       # noqa: BLE001
            continue
        # The control itself is kept so a later step can ask it for children; it is
        # stripped before the report is serialised, and is not part of the comparison.
        collected.append({"role": role, "name": name, "depth": depth + 1,
                          "patterns": patterns, "control": child})
        collected.extend(_uia_walk(child, depth + 1, limit - len(collected)))
    return collected


def _uia_cell(table) -> object:
    """The text UIA reports for a cell, or why it could not be read."""
    try:
        cells = table["control"].GetChildren()
    except Exception as exc:                    # noqa: BLE001
        return Unavailable("could not read the UIA table's children", str(exc))
    if not cells:
        return Absent("the UIA table reported no children")
    index = min(6, len(cells) - 1)
    try:
        return {"index": index, "role": cells[index].ControlTypeName,
                "text": cells[index].Name or "", "of": len(cells)}
    except Exception as exc:                    # noqa: BLE001
        return Unavailable("could not read the UIA cell", str(exc))


def _counts(values) -> dict:
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _unmeasured(value) -> bool:
    """True when this is a failure to measure, rather than a measured absence.

    The distinction the whole script turns on, and it has to be a type test: the
    rendered string cannot carry it, which is exactly what made every absence look
    like an unanswered question.
    """
    return isinstance(value, Unavailable) and not isinstance(value, Absent)


def describe(value) -> str:
    if isinstance(value, Absent):
        return f"ABSENT ({value.reason})"
    if isinstance(value, Unavailable):
        return f"UNAVAILABLE ({value.reason})"
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items() if k != "control")
    return str(value)


def report(jab_report: dict, uia_report: dict) -> tuple:
    """The side-by-side table, and whether every measurement was actually taken.

    The second return value is the point: a row where either side could not be
    measured is an unanswered question, not a win. A row where a side measured and
    found *nothing* is an answer -- that is what Absent records, and it is the plan's
    own clear-win row.
    """
    lines = []
    complete = True

    client = uia_report.get("_client")
    if isinstance(client, Unavailable):
        lines.append(f"  UIA side could not be measured: {client.reason}")
        if client.detail:
            lines.append(f"      {client.detail.strip().splitlines()[0][:100]}")
        lines.append("      Every UIA row below is UNANSWERED, not zero. Install the "
                     "client and rerun.")
        complete = False
        uia_report = {}

    width = max(len(label) for _key, label in QUESTIONS) + 2
    lines.append(f"  {'question'.ljust(width)} {'pyjab (JAB)':<34} {'UIA':<34}")
    lines.append(f"  {'-' * width} {'-' * 34} {'-' * 34}")
    for key, label in QUESTIONS:
        jab_value = jab_report.get(key, Unavailable("not reported by the JAB side"))
        uia_value = uia_report.get(key, Unavailable("not measured"))
        left, right = describe(jab_value), describe(uia_value)
        # A type test, not the rendered string: only a failure to measure makes the
        # run incomplete. This is the line that used to put verdict()'s clear-win
        # branch out of reach.
        if _unmeasured(jab_value) or _unmeasured(uia_value):
            complete = False
        lines.append(f"  {label.ljust(width)} {left[:34]:<34} {right[:34]:<34}")

    lines.append("")
    lines.append("  pyjab roles: " + ", ".join(
        f"{k} x{v}" for k, v in list(jab_report.get("role_counts", {}).items())[:12]))
    if uia_report:
        lines.append("  UIA   roles: " + ", ".join(
            f"{k} x{v}" for k, v in list(uia_report.get("role_counts", {}).items())[:12]))
    return lines, complete


def verdict(jab_report: dict, uia_report: dict, complete: bool) -> str:
    """The plan's three outcomes, from the numbers -- not from an impression.

    Ordered so that the one unambiguous answer wins first: whether each side can read a
    table cell's text. That is the plan's own example of a clear win, and it does not
    depend on counting anything.

    Where both can, the comparison is on **named** elements rather than on the total. A
    larger tree is not a more useful one -- every extra unnamed node is context an agent
    has to be shown and cannot act on -- so a total-element ratio would reward the wrong
    thing.
    """
    if not complete:
        return ("INCONCLUSIVE: at least one side could not be measured. The plan's "
                "decision table needs both; see the UNANSWERED rows above.")

    def cell_text(report):
        cell = report.get("cell")
        return cell.get("text", "") if isinstance(cell, dict) else None

    jab_text, uia_text = cell_text(jab_report), cell_text(uia_report)

    if jab_text and not uia_text:
        return ("JAB CLEARLY BETTER on the plan's own test: pyjab reads a table cell's "
                "text and UIA reports none. Continue the MCP direction.")
    if uia_text and not jab_text:
        return ("UIA LOOKS BETTER: it reads a table cell's text and pyjab reports none. "
                "The plan says stop the MCP direction and put the effort into the "
                "library. Confirm by hand first.")

    jab_named = jab_report.get("named") or 0
    uia_named = uia_report.get("named") or 0
    ratio = (uia_named / jab_named) if jab_named else None

    if jab_text and uia_text:
        if ratio is not None and ratio > 1.5:
            return (f"UIA LOOKS BETTER on information: both read the cell, and UIA "
                    f"exposes {uia_named} named elements against pyjab's {jab_named} "
                    f"({ratio:.1f}x). The plan says stop the MCP direction. Check by "
                    f"hand first -- these may be duplicates or containers, which are "
                    f"noise rather than detail.")
        return ("ABOUT THE SAME: both read the table cell and UIA does not expose "
                "materially more named elements. Downgrade pyjab-mcp to an optional "
                "backend rather than a product.")
    return ("INCONCLUSIVE from these numbers alone: neither side read the table cell. "
            "Read the table above against the plan's decision table "
            "(docs/PYJAB_MCP_PLAN.md section 2.3). What the script cannot judge is "
            "whether the *fields* either side exposes are the ones an agent needs.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--title", required=True,
                        help="window title, as pyjab-inspect windows prints it")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Windows":
        print("M0 needs Windows: pyjab drives the Java Access Bridge, and UIA is a "
              "Windows API. Nothing here can be measured elsewhere.", file=sys.stderr)
        return 2

    jab_report = jab_side(args.title, args.timeout)
    uia_report = uia_side(args.title, args.timeout)
    lines, complete = report(jab_report, uia_report)
    conclusion = verdict(jab_report, uia_report, complete)

    if args.json:
        def plain(value):
            if isinstance(value, Unavailable):
                # explicit, because the distinction is invisible in the output
                # otherwise and it is the difference between an answer and a gap
                return {"unavailable": value.reason,
                        "measured_absence": isinstance(value, Absent),
                        "detail": value.detail}
            if isinstance(value, dict):
                return {k: plain(v) for k, v in value.items() if k != "control"}
            return value
        print(json.dumps({"title": args.title, "pyjab": plain(jab_report), "uia": plain(uia_report),
                          "complete": complete, "verdict": conclusion},
                         indent=2, ensure_ascii=False))
        return 0 if complete else 1

    print(f"\nM0 comparison for {args.title!r}\n")
    print("\n".join(lines))
    print(f"\n  {conclusion}\n")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
