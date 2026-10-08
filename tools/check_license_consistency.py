#!/usr/bin/env python
"""Check that the licence pyjab claims is the licence pyjab actually ships.

Why this exists
---------------
Changing licence touches four places: the ``LICENSE`` file, ``[project].license``
in ``pyproject.toml``, the bullet in the README, and the licence section of the
docs.  Nothing about editing one of them reminds you about the others, and the
failure is silent -- a package whose metadata says Apache-2.0 while shipping the
MIT text tells users something untrue about their own obligations, and the first
person to notice is a lawyer.

This reads the ``LICENSE`` text, works out which licence it is from its own
wording, and compares that with what the metadata and the README claim.  Run it
whenever a licence changes; CI runs it on every push.

Usage
-----
    python tools/check_license_consistency.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11 and later
except ModuleNotFoundError:  # pragma: no cover - depends on the interpreter
    try:
        # pyjab supports Python 3.9, which predates tomllib.  tomli is the same
        # library under the name it had before it entered the standard library,
        # and is in the dev extra for exactly this reason.
        import tomli as tomllib
    except ModuleNotFoundError:
        sys.exit(
            "reading pyproject.toml needs tomllib (Python 3.11+) or tomli.\n"
            "  Install it with: pip install tomli"
        )

REPO_ROOT = Path(__file__).resolve().parent.parent

#: SPDX id, then phrases that must all appear in the licence text.  The order
#: matters and is not alphabetical: the LGPL and the AGPL both quote the GPL's
#: heading, and the BSD-3 text contains the whole of the BSD-2 text, so the more
#: specific rule has to be tried first.
KNOWN_LICENCES = (
    ("AGPL-3.0-only", ("GNU AFFERO GENERAL PUBLIC LICENSE", "Version 3")),
    ("LGPL-3.0-only", ("GNU LESSER GENERAL PUBLIC LICENSE", "Version 3")),
    ("LGPL-2.1-only", ("GNU LESSER GENERAL PUBLIC LICENSE", "Version 2.1")),
    ("GPL-3.0-only", ("GNU GENERAL PUBLIC LICENSE", "Version 3")),
    ("GPL-2.0-only", ("GNU GENERAL PUBLIC LICENSE", "Version 2")),
    ("Apache-2.0", ("Apache License", "Version 2.0, January 2004")),
    ("MPL-2.0", ("Mozilla Public License", "Version 2.0")),
    ("MIT", ("Permission is hereby granted, free of charge",
             "WITHOUT WARRANTY OF ANY KIND")),
    ("ISC", ("Permission to use, copy, modify, and/or distribute this software",)),
    ("BSD-3-Clause", ("Redistribution and use in source and binary forms",
                      "Neither the name of")),
    ("BSD-2-Clause", ("Redistribution and use in source and binary forms",)),
)

#: The module attribute a user reads with ``pyjab.__license__``.
MODULE_LICENCE = re.compile(r'^__license__\s*=\s*"(?P<value>[^"]*)"', re.MULTILINE)

#: The copyright line at the top of a licence file.
COPYRIGHT = re.compile(
    r"^\s*Copyright\s*(?:\(c\)|©)?\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?\s+)?"
    r"(?P<holder>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

#: How a licence is likely to be named in prose, for the README check.  The
#: README is written for people, not for package managers, so it says "GPLv2" and
#: "MIT" rather than an SPDX identifier.
PROSE_NAMES = {
    "MIT": ("MIT",),
    "Apache-2.0": ("Apache", "Apache-2.0", "Apache 2.0"),
    "BSD-3-Clause": ("BSD-3-Clause", "BSD 3-Clause", "BSD"),
    "BSD-2-Clause": ("BSD-2-Clause", "BSD 2-Clause", "BSD"),
    "ISC": ("ISC",),
    "MPL-2.0": ("MPL", "Mozilla Public License"),
    "GPL-2.0-only": ("GPLv2", "GPL-2.0", "GPLv2.0", "GNU General Public License v2"),
    "GPL-3.0-only": ("GPLv3", "GPL-3.0", "GNU General Public License v3"),
    "LGPL-2.1-only": ("LGPLv2.1", "LGPL-2.1", "LGPLv2"),
    "LGPL-3.0-only": ("LGPLv3", "LGPL-3.0"),
    "AGPL-3.0-only": ("AGPLv3", "AGPL-3.0"),
}


def names_the_licence(text: str, names) -> list:
    """Which of ``names`` appear in ``text`` as words rather than as substrings.

    Substring matching is useless here: "ISC" is inside "discussion", "MIT" is
    inside "commit", and "MPL" is inside "example". Using it made this script
    report that CONTRIBUTING.rst mentions three licences it has never heard of.
    """
    found = []
    for name in names:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(name)
    return found


#: Files in docs/ that are maintainer notes rather than published documentation.
#: They are listed in .gitignore and excluded from the sdist, so a checkout has
#: them but a tarball does not -- which is why they are named here rather than
#: discovered from git.
INTERNAL_NOTES = frozenset({
    "TRIAGE.md", "ROADMAP.md", "PYJAB_MCP_PLAN.md", "ISSUE_REPLIES.md",
    "CONSENT_REQUESTS.md",
})

#: The two shapes a statement of *pyjab's* licence takes: the sentence, and the
#: metadata bullet.  Deliberately narrow, and it has to be.  docs/2 discusses the
#: licence of the Java Access Bridge that ships inside the JDK -- "is GPLv2 with
#: the Classpath Exception", about Oracle's code rather than pyjab's -- and a rule
#: that reacted to any mention of a licence would report that page as stale the
#: moment pyjab changed licence, which is the wrong answer delivered confidently.
LICENCE_CLAIM = re.compile(
    r"(?:pyjab\s+is\s+licen[cs]ed\s+under|\*\*Licen[cs]e:\*\*)"
    r"\s*(?P<stated>[^\n.]+)",
    re.IGNORECASE,
)


def as_display_path(path: Path) -> str:
    """A path relative to the project root, always with forward slashes.

    ``Path.relative_to`` yields backslashes on Windows, so without this the same
    finding is reported as ``docs/1-Overview.md`` here and ``docs\\1-Overview.md``
    there. Output that changes with the platform is harder to search, harder to
    match in a test, and different for no reason.
    """
    return path.relative_to(REPO_ROOT).as_posix()


def places_that_state_the_licence(root: Path) -> list:
    """Every published file that claims a licence, in a stable order."""
    found = []
    readme = root / "README.rst"
    if readme.is_file():
        found.append(readme)
    for path in sorted((root / "docs").glob("*.md")):
        if path.name not in INTERNAL_NOTES:
            found.append(path)
    return found


def stated_licences(text: str) -> list:
    """The licence named by each claim in ``text``, with its line number."""
    claims = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in LICENCE_CLAIM.finditer(line):
            claims.append((number, match.group("stated").strip()))
    return claims


def copyright_holder(text: str) -> str:
    """The holder named by a licence file's copyright line, if it has one.

    Matches the year range whether or not it is there, since MIT files are
    written both ways, and stops at the end of the line.
    """
    match = COPYRIGHT.search(text)
    return match.group("holder").strip() if match else ""


def identify(text: str) -> str | None:
    """The SPDX id of the licence whose wording this is, or None."""
    for spdx, phrases in KNOWN_LICENCES:
        if all(phrase in text for phrase in phrases):
            return spdx
    return None


def declared_in_pyproject(path: Path) -> str:
    """The SPDX expression in ``[project].license``, as written."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    declared = data.get("project", {}).get("license")

    if declared is None:
        sys.exit("pyproject.toml has no [project].license")
    if isinstance(declared, dict):  # the pre-PEP 639 spelling
        # `{text = "GPLv2"}` or `{file = "LICENSE"}` -- neither is an SPDX id, so
        # there is nothing to compare against and the file form is checked below.
        return declared.get("text", "")
    return str(declared)


def licence_paths(pyproject: Path, root: Path) -> list:
    """Every file ``[project].license-files`` names, resolved."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    patterns = data.get("project", {}).get("license-files") or ["LICENSE"]

    found = []
    for pattern in patterns:
        # The globs are relative to the project root and may match several files.
        found.extend(sorted(root.glob(pattern)))
    return found


def main() -> int:
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        sys.exit(f"no pyproject.toml in {REPO_ROOT}")

    files = licence_paths(pyproject, REPO_ROOT)
    if not files:
        sys.exit("no licence file found; check [project].license-files")

    print("licence files:")
    for path in files:
        print(f"  {as_display_path(path)}")

    # The main licence file is the one that identifies the project's terms.
    primary = files[0]
    text = primary.read_text(encoding="utf-8", errors="replace")
    detected = identify(text)
    declared = declared_in_pyproject(pyproject)

    print(f"\n{as_display_path(primary)} reads as: {detected or 'UNRECOGNISED'}")
    print(f"pyproject.toml declares:  {declared or '(nothing)'}")

    problems = []

    if detected is None:
        problems.append(
            f"the text of {primary.name} does not match any licence this check "
            "knows. Add its wording to KNOWN_LICENCES in this script, so that the "
            "rest of the check can run."
        )
    elif declared and declared.strip() != detected:
        problems.append(
            f"pyproject.toml says {declared!r} but {primary.name} is {detected!r}. "
            "These ship together, so one of them is wrong -- and the metadata is "
            "what package managers and licence scanners read."
        )

    # Every published file that states the licence, not just the README.  The
    # relicensing commit has to touch all of them, and the first version of this
    # check looked only at README.rst -- leaving docs/1-Overview.md and
    # docs/Home.md, which both say it in as many words, entirely unguarded.
    for path in places_that_state_the_licence(REPO_ROOT):
        relative = as_display_path(path)
        for number, stated in stated_licences(path.read_text(encoding="utf-8")):
            if detected is None:
                break
            names = PROSE_NAMES.get(detected, ())
            if names and not names_the_licence(stated, names):
                problems.append(
                    f"{relative}:{number} states {stated!r}, which does not name "
                    f"{detected!r}. Expected one of: {', '.join(names)}."
                )
            else:
                print(f"{relative + ':' + str(number):<28} agrees: {stated}")

    # CONTRIBUTING explains the relicensing, so it is expected to name licences
    # other than the current one.  Reported rather than enforced.
    contributing = REPO_ROOT / "CONTRIBUTING.rst"
    if contributing.is_file() and detected:
        body = contributing.read_text(encoding="utf-8")
        stale = [
            other for other, other_names in PROSE_NAMES.items()
            if other != detected
            and names_the_licence(body, other_names)
            and detected.replace("-only", "") not in other
        ]
        if stale:
            print(
                f"\n  note: CONTRIBUTING.rst also mentions "
                f"{', '.join(sorted(stale))} -- expected, since it explains the "
                "relicensing. Check it reads as history rather than as the "
                "current licence."
            )

    # The copyright line is the licence's operative sentence about who holds it,
    # and the README restates it. The README said "Gary Gao" while the LICENSE
    # said "Gary Gao and contributors" -- which is the difference between
    # crediting the people whose consent made the change possible and not.
    holder = copyright_holder(text)
    readme = REPO_ROOT / "README.rst"
    if holder and readme.is_file():
        if holder.lower() not in readme.read_text(encoding="utf-8").lower():
            problems.append(
                f"{primary.name} names {holder!r} as the copyright holder and the "
                "README does not. They ship together; the LICENSE is the one that "
                "counts, so the README is the one to correct."
            )
        else:
            print(f"README names the holder:  {holder}")

    # The module attribute, which is what `import pyjab; pyjab.__license__` reads.
    # It said GPLv2 in the 1.6.0 wheel while the same wheel's METADATA said
    # License-Expression: MIT -- two answers in one installation, and this check
    # did not look at the one a user is most likely to see.
    module = REPO_ROOT / "pyjab" / "__init__.py"
    if module.is_file() and declared:
        in_module = MODULE_LICENCE.search(module.read_text(encoding="utf-8"))
        if in_module is None:
            problems.append(
                f"{module.relative_to(REPO_ROOT).as_posix()} has no __license__, so "
                "`pyjab.__license__` raises.  It is part of the interface."
            )
        elif in_module.group("value") != declared:
            problems.append(
                f"pyjab/__init__.py says __license__ = {in_module.group('value')!r} "
                f"but pyproject.toml declares {declared!r}.  Both are shipped in the "
                "same wheel and a user can read either."
            )
        else:
            print(f"pyjab.__license__ agrees: {in_module.group('value')}")

    if problems:
        print("\nFAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nPASSED: the licence pyjab declares is the licence pyjab ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
