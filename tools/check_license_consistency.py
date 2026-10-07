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
import tomllib
from pathlib import Path

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


def readme_mentions(readme: Path) -> str:
    """The README's licence bullet, for the prose check."""
    text = readme.read_text(encoding="utf-8")
    for line in text.splitlines():
        if re.search(r"\*\*Licen[cs]e:\*\*", line) or line.strip().startswith("Licen"):
            return line.strip()
    return ""


def main() -> int:
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        sys.exit(f"no pyproject.toml in {REPO_ROOT}")

    files = licence_paths(pyproject, REPO_ROOT)
    if not files:
        sys.exit("no licence file found; check [project].license-files")

    print("licence files:")
    for path in files:
        print(f"  {path.relative_to(REPO_ROOT)}")

    # The main licence file is the one that identifies the project's terms.
    primary = files[0]
    text = primary.read_text(encoding="utf-8", errors="replace")
    detected = identify(text)
    declared = declared_in_pyproject(pyproject)

    print(f"\n{primary.relative_to(REPO_ROOT)} reads as: {detected or 'UNRECOGNISED'}")
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

    readme = REPO_ROOT / "README.rst"
    if readme.is_file():
        mention = readme_mentions(readme)
        if detected and mention:
            names = PROSE_NAMES.get(detected, ())
            if names and not names_the_licence(mention, names):
                problems.append(
                    f"README says {mention!r}, which does not name {detected!r}. "
                    f"Expected one of: {', '.join(names)}."
                )
            else:
                print(f"README bullet agrees:     {mention}")

    # Anything else that names the old licence in a place users read.
    for name in ("CONTRIBUTING.rst",):
        path = REPO_ROOT / name
        if path.is_file() and detected:
            names = PROSE_NAMES.get(detected, ())
            body = path.read_text(encoding="utf-8")
            stale = [
                other for other, other_names in PROSE_NAMES.items()
                if other != detected
                and names_the_licence(body, other_names)
                and detected.replace("-only", "") not in other
            ]
            if stale:
                print(
                    f"\n  note: {name} also mentions {', '.join(sorted(stale))}. "
                    "That may be deliberate -- it explains the relicensing -- but "
                    "check it reads as history rather than as the current licence."
                )

    if problems:
        print("\nFAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("\nPASSED: the licence pyjab declares is the licence pyjab ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
