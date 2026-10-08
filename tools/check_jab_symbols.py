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

Two ways to check, and the first is the better one.

**Against the DLL you actually have.**  ``--dll`` loads the bridge and asserts that
every declared symbol resolves.  This is the strongest form of the check, because
it is the artefact pyjab will call rather than a description of it, and because a
JDK that stops exporting something is caught the moment it is installed.

**Against ``WinAccessBridge.DEF``.**  ``--def`` reads the export list from a file.
This is what the working agreement names, and it is useful offline -- but note that
the DEF is part of the **OpenJDK source tree**
(``src/jdk.accessibility/windows/native/libwindowsaccessbridge/``) and is **not
shipped inside an installed JDK**.  The first version of this tool assumed it was,
looked under ``JAVA_HOME``, and found nothing on a runner with Temurin 17.

Usage
-----
    python tools/check_jab_symbols.py
    python tools/check_jab_symbols.py --def "C:\\path\\to\\WinAccessBridge.DEF"
    python tools/check_jab_symbols.py --dll "C:\\path\\to\\WindowsAccessBridge-64.dll"

With neither, it loads the bridge the way pyjab does and checks against that.
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


def find_dll(explicit: str | None) -> str:
    """The bridge DLL to check, found the way pyjab finds it."""
    from pyjab.config import find_bridge_dll

    found = find_bridge_dll(explicit)
    if not found:
        sys.exit(
            "could not find the Java Access Bridge DLL.\n"
            "  This check needs a JDK, which is what installs it. Pass one\n"
            "  explicitly with --dll if it is somewhere unusual."
        )
    return str(found)


def check_against_dll(dll_path: str, declared: list) -> list:
    """Every declared symbol the DLL does not export.

    ``getattr`` on a ``ctypes`` DLL is the same lookup the declaration step
    performs, which is the point: this asks the same question the code will, of
    the same library.
    """
    from ctypes import CDLL

    try:
        bridge = CDLL(dll_path)
    except OSError as exc:
        sys.exit(f"could not load {dll_path}:\n  {exc}")

    return [name for name in declared if not hasattr(bridge, name)]


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
                        help="check against a WinAccessBridge.DEF file instead")
    parser.add_argument("--dll", dest="dll_path", default=None,
                        help="the bridge DLL to check, instead of discovering one")
    args = parser.parse_args()

    declared = declared_symbols()

    if args.def_path:
        return report_against_def(args.def_path, declared)
    return report_against_dll(args.dll_path, declared)


def report_against_dll(explicit: str | None, declared: list) -> int:
    """Check the declarations against the library they will be used on."""
    dll_path = find_dll(explicit)
    print(f"DLL:      {dll_path}")

    missing = check_against_dll(dll_path, declared)

    print(f"declared: pyjab/jabfixedfunc.py")
    print(f"          {len(declared)} signatures")

    if missing:
        print(f"\nFAILED: {len(missing)} declared symbol(s) this bridge does not export:")
        for name in missing:
            print(f"  - {name}")
        print(
            "\n  These are typos, or names from a header this JDK does not implement.\n"
            "  _fix_bridge_function logs them and returns, so the declaration silently\n"
            "  does not apply -- and ctypes then truncates any 64-bit argument to a\n"
            "  C int, which produces a wrong answer rather than an error."
        )
        return 1

    print(f"\nPASSED: every declared symbol is exported by this bridge.")
    print("\n  Checked against the library rather than a list of names, so a JDK that\n"
          "  stops exporting one is caught when it is installed.")
    return 0


def report_against_def(def_path: str, declared: list) -> int:
    """Check the declarations against a DEF file, offline."""
    defined = find_def(def_path)
    exported = exported_symbols(defined)

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
