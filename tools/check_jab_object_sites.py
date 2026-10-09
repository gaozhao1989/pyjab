#!/usr/bin/env python
"""Every JAB call that hands out a Java object, and where its reference goes.

The audit the project calls P1-2, made mechanical.

Why this exists
---------------

Java Access Bridge hands out a **reference** every time it returns an object, and the
reference has to be released exactly once. Obtaining the same object twice means
releasing it twice; using a handle after its last release is use-after-free. Neither
fails loudly at the point of the mistake -- the first corrupts a count and the second
reads a dead handle -- and the symptom people report is "it gets slower until it
stalls", which is why issue #43 sat unexplained for years.

One leak has been found this way: ``_xpath_search_root()`` took a reference on every
absolute xpath lookup and nothing ever released it. That is **not** an explanation of
#43 and is not offered as one. What it does show is that the rule has been broken in
this codebase, in a path that every user takes, and that reading the code did not find
it.

Why a registry rather than a dataflow analysis
---------------------------------------------

Reachability of a release is not decidable by reading a call site: the reference is
often *returned*, and whether that is correct depends on what the caller does. A checker
that tried to prove it would either be wrong or be a research project.

So this records the **disposition** of every reference and checks that the set of
reference-producing call sites has not changed. The failure it prevents is the one that
actually happens: a new call site is added, a reference appears, and nothing anywhere
notices. Adding one now fails CI until somebody writes down where the reference goes.

The disposition is prose, because it is a judgement. The **set** is not, and that is the
part that is enforced.

How the set is derived
----------------------

From ``pyjab/jabfixedfunc.py``'s ``SIGNATURES`` table: a symbol hands out a reference if
its result type is ``JOBJECT64`` or if any argument type is ``POINTER(JOBJECT64)``. That
is the definition rather than a hand-written list, so a symbol added to the table is
covered without anyone remembering to add it here.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SIGNATURE_SOURCE = REPO_ROOT / "pyjab" / "jabfixedfunc.py"

#: ``(file, enclosing function, symbol)`` -> where the reference goes.
#:
#: Audited by reading, and two of the seven are exercised by
#: ``tests/test_object_lifetimes.py`` against the reference-counting bridge. The
#: driver-side ones cannot be: they run inside ``JABDriver.__init__`` and need a live
#: Java window. Those say so rather than implying the same evidence for all seven.
SITES = {
    ("pyjab/jabdriver.py", "_get_accessible_context_from_hwnd",
     "getAccessibleContextFromHWND"):
        "Returns the pair to init_jab, its only caller, which stores it as "
        "self.accessible_context and holds it for the lifetime of the driver -- which "
        "is why every JABElement it creates carries it. Not released, and must not be: "
        "it is the handle the whole object graph hangs from. Read, not exercised: it "
        "runs inside __init__.",

    ("pyjab/jabdriver.py", "init_jab", "getTopLevelObject"):
        "Released immediately after the one call that uses it, to turn a vmid and a "
        "context into an hwnd. This was the second leak: nothing released it, so every "
        "driver constructed from a vmid and a context left one Java object behind. That "
        "is one per driver rather than one per lookup, which is why it was not noticed "
        "-- and the reason it was found is this checker rather than reading, since the "
        "hand inventory of call sites missed this call twice.",

    ("pyjab/jabdriver.py", "_focused_context", "getAccessibleContextWithFocus"):
        "Returns the context to get_focused_element, which wraps it in a JABElement and "
        "returns that -- so the caller owns one reference, the same contract as "
        "find_element_by_*. Read, not exercised: needs a live window with focus.",

    ("pyjab/jabelement.py", "_get_accessible_parent_from_context",
     "getAccessibleParentFromContext"):
        "Returned to _search_path's `..` branch, which appends it to `examined` unless "
        "it is the answer, so the caller releases it once the search is over. Exercised "
        "by tests/test_xpath_ownership.py, whose battery includes /.. in both modes.",

    ("pyjab/jabelement.py", "_get_top_level_object", "getTopLevelObject"):
        "Returned to _xpath_search_root, which releases it in a finally block after the "
        "walk. This is the leak that was found: it used to be released nowhere, so every "
        "absolute xpath lookup left one Java object behind. Exercised by "
        "tests/test_xpath_ownership.py and tests/test_xpath_traversal.py.",

    ("pyjab/jabelement.py", "_generate_childs_from_element",
     "getAccessibleChildFromContext"):
        "Yielded to the caller, which owns each child -- the contract get_children() "
        "documents. Exercised by tests/test_object_lifetimes.py and every traversal "
        "test.",

    ("pyjab/jabelement.py", "_get_accessible_selection_from_context_index",
     "getAccessibleSelectionFromContext"):
        "The one site that releases its own reference before returning, because it "
        "returns the selection index rather than the object. Exercised by "
        "tests/test_table_selection.py.",
}


def handed_out_symbols(source: Path = SIGNATURE_SOURCE) -> set:
    """The JAB symbols that give the caller a reference to a Java object."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    signatures = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SIGNATURES"
                for t in node.targets)
    )
    found = set()
    for entry in signatures.value.elts:
        name = entry.elts[0].value
        result_type = ast.unparse(entry.elts[1])
        argument_types = ast.unparse(entry.elts[2])
        if result_type == "JOBJECT64" or "POINTER(JOBJECT64)" in argument_types:
            found.add(name)
    if not found:
        sys.exit("no reference-producing symbols found; SIGNATURES has changed shape")
    return found


def call_sites(symbols: set) -> set:
    """``(relative file, enclosing function, symbol)`` for every call in pyjab/."""
    sites = set()
    for path in sorted((REPO_ROOT / "pyjab").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        relative = path.relative_to(REPO_ROOT).as_posix()
        for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                called = node.func
                name = (called.attr if isinstance(called, ast.Attribute)
                        else called.id if isinstance(called, ast.Name) else None)
                if name in symbols:
                    sites.add((relative, function.name, name))
    return sites


def main() -> int:
    symbols = handed_out_symbols()
    actual = call_sites(symbols)
    recorded = set(SITES)

    print(f"{len(symbols)} JAB symbol(s) hand out a reference:")
    for name in sorted(symbols):
        print(f"  {name}")

    print(f"\n{len(actual)} call site(s) in pyjab/:")

    added = sorted(actual - recorded)
    removed = sorted(recorded - actual)

    for site in sorted(actual):
        note = SITES.get(site)
        marker = "NEW " if site in added else "    "
        print(f"  {marker}{site[0]}:{site[1]} -> {site[2]}")
        if note:
            print(f"        {note}")

    if added or removed:
        print()
        for site in removed:
            print(f"  ::error:: {site[0]}:{site[1]} no longer calls {site[2]}")
        print()
        print("FAILED: the set of reference-producing call sites has changed.")
        print()
        print("  This is the check that exists because nobody notices a new reference.")
        print("  For each site marked NEW, work out where the reference goes -- who")
        print("  releases it, and whether that is once -- and add it to SITES in this")
        print("  script with that reasoning. For one that has gone, remove its entry.")
        print()
        print("  If the reference is returned, the answer is about the caller, which")
        print("  is a judgement. If it is stored, say for how long. Do not write")
        print("  'released' without saying where.")
        return 1

    print(f"\nPASSED: all {len(actual)} reference-producing call sites are accounted for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
