#!/usr/bin/env python
"""Check pyjab's JAB signatures against the symbols the DLL actually exports.

Why this exists
---------------
``pyjab/jabfixedfunc.py`` tells ctypes the type of every Java Access Bridge
function it calls.  Get a *name* wrong and nothing complains at the point of the
mistake: ``_fix_bridge_function`` logs that the symbol was not found and returns,
so the call site later fails with an ``AttributeError`` — or, worse, the
declaration silently does not apply and ctypes truncates 64-bit arguments to C
``int``.  A wrong signature produces wrong answers rather than exceptions.

The authoritative list of what the bridge exports is ``WinAccessBridge.DEF``,
which ships inside the JDK's Java Access Bridge.  This compares the two.

Usage
-----
    python tools/check_jab_symbols.py
    python tools/check_jab_symbols.py --def "C:\\path\\to\\WinAccessBridge.DEF"

Without ``--def`` it looks in the usual places under ``JAVA_HOME`` and the
standard JDK installation roots.  The DEF file is read, never copied: only the
list of names matters, and the names are the interface.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: Where a JDK keeps the DEF, relative to its root.
DEF_RELATIVE_PATHS = (
    r"jre\bin\WinAccessBridge.DEF",
    r"bin\WinAccessBridge.DEF",
    r"lib\WinAccessBridge.DEF",
    r"jre\lib\WinAccessBridge.DEF",
)

DEF_NAME = "WinAccessBridge.DEF"

_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def find_def(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            sys.exit(f"no such file: {path}")
        return path

    roots: list[Path] = []
    for env_var in ("JAVA_HOME", "JDK_HOME"):
        value = os.environ.get(env_var)
        if value:
            roots.append(Path(value))
    for pattern in (r"C:\Program Files\Java", r"C:\Program Files\Eclipse Adoptium",
                    r"C:\Program Files\Microsoft", r"C:\Program Files\Zulu",
                    os.path.expanduser(r"~\.jdks")):
        root = Path(pattern)
        if root.is_dir():
            roots.extend(sorted(p for p in root.iterdir() if p.is_dir()))

    for root in roots:
        for relative in DEF_RELATIVE_PATHS:
            candidate = root / relative
            if candidate.is_file():
                return candidate
        for found in root.glob(f"**/{DEF_NAME}"):
            return found

    sys.exit(
        f"could not find {DEF_NAME}.\n"
        "  It ships with the Java Access Bridge inside a JDK, usually at\n"
        r"  <JAVA_HOME>\jre\bin\WinAccessBridge.DEF" + "\n"
        "  Pass it explicitly with --def if it is somewhere else."
    )


def exported_symbols(path: Path) -> set:
    """The names in a DEF file's EXPORTS section.

    A DEF line is either a bare symbol, a symbol with an ordinal
    (``name @12``), a symbol with a different exported name (``name=internal``),
    or a keyword.  Comments start with ``;``.
    """
    symbols = set()
    in_exports = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        keyword = line.split()[0].upper()
        if keyword in ("EXPORTS", "SECTIONS", "IMPORTS"):
            in_exports = keyword == "EXPORTS"
            continue
        if keyword in ("LIBRARY", "DESCRIPTION", "STACKSIZE", "HEAPSIZE",
                       "NAME", "VERSION", "BASE", "DATA"):
            continue
        if not in_exports:
            continue
        token = line.split()[0].split("@")[0].split("=")[0].strip()
        if _SYMBOL.match(token):
            symbols.add(token)
    return symbols


def declared_symbols() -> list:
    from pyjab.jabfixedfunc import SIGNATURES

    return [entry[0] for entry in SIGNATURES]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--def", dest="def_path", default=None,
                        help="path to WinAccessBridge.DEF")
    args = parser.parse_args()

    defined = find_def(args.def_path)
    exported = exported_symbols(defined)
    declared = declared_symbols()

    print(f"DEF:      {defined}")
    print(f"          {len(exported)} exported symbols")
    print(f"declared: pyjab/jabfixedfunc.py")
    print(f"          {len(declared)} signatures")

    if len(declared) != len(set(declared)):
        duplicates = sorted({n for n in declared if declared.count(n) > 1})
        print(f"\nFAILED: declared more than once: {', '.join(duplicates)}")
        return 1

    missing = sorted(set(declared) - exported)
    if missing:
        print(f"\nFAILED: {len(missing)} declared symbol(s) the bridge does not export:")
        for name in missing:
            print(f"  - {name}")
        print(
            "\n  These are typos or names from a different header.  _fix_bridge_function\n"
            "  logs them at runtime and returns, so the declaration silently does not\n"
            "  apply -- and ctypes then truncates any 64-bit argument to a C int."
        )
        return 1

    unused = sorted(exported - set(declared))
    print(f"\nPASSED: every declared symbol is exported by the bridge.")
    if unused:
        print(f"\n  {len(unused)} exported symbol(s) pyjab does not declare, which is")
        print("  fine -- only what is called needs a signature. A few are interesting:")
        for name in unused:
            if "Table" in name or "Selection" in name:
                print(f"    - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
