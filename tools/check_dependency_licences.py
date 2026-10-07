#!/usr/bin/env python
"""Refuse a dependency whose licence would constrain pyjab's users.

Why this exists
---------------
pyjab is GPLv2 because that is what it inherited, and it is on its way to a
permissive licence.  A copyleft dependency added in the meantime would either
block that move or impose terms on everyone who installs pyjab, and neither is
the kind of thing to discover when a lawyer asks.  This catches it when the
dependency is added.

It is deliberately a list of licences to refuse rather than a list to allow.  An
unusual permissive licence -- CMU, Zope, historical BSD wordings -- should not
break the build, whereas GPL, AGPL and the rest must every time.

Usage
-----
    pip install . pip-licenses
    python tools/check_dependency_licences.py

Exits non-zero, and names the offender, if anything pyjab depends on is under one
of them.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import requires
from importlib.metadata import version

#: Substrings that mark a licence as one to refuse.  ``GPL`` covers ``LGPL`` and
#: ``AGPL``; the rest are the strong-copyleft and source-available licences that
#: are not compatible with distributing pyjab under a permissive one.
REFUSED = (
    "GPL",
    "General Public License",
    "Affero",
    "SSPL",
    "EUPL",
    "OSL",
    "CPAL",
    "CDDL",
    "Sleepycat",
    "RPL",
    "CC-BY-SA",
    "Commons Clause",
)

#: The project itself is GPLv2, which is the whole reason for the check.
SELF = "pyjab"

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def runtime_requirement_names(declared) -> set:
    """The distribution names in a ``Requires-Dist`` list, extras excluded.

    Split out from the metadata lookup so that the parsing can be tested without
    pyjab installed as a distribution -- which is the normal state of a checkout,
    and the reason an earlier version of this checked nothing in the portable
    suite while appearing to pass.
    """
    names = set()
    for requirement in declared:
        # An extra is opt-in, so a dev-only dependency must not be gated.
        if "extra ==" in requirement:
            continue
        match = _REQUIREMENT_NAME.match(requirement)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def direct_requirement_names() -> set:
    """The distributions pyjab declares a dependency on, normalised.

    Read from the installed metadata rather than from pyproject.toml, because what
    matters is the licence of the distribution that would actually be installed.
    """
    try:
        declared = requires(SELF) or []
    except PackageNotFoundError:
        sys.exit(
            f"{SELF} is not installed, so there is nothing to check.\n"
            "  Run: pip install ."
        )
    return runtime_requirement_names(declared)


def installed_licences() -> dict:
    """Every installed distribution's licence, via pip-licenses."""
    result = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json", "--with-urls"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(
            "pip-licenses is not available or failed.\n"
            f"  {result.stderr.strip()}\n"
            "  Install it with: pip install pip-licenses"
        )

    out = {}
    for entry in json.loads(result.stdout):
        name = entry.get("Name", "").lower().replace("_", "-")
        out[name] = {
            "version": entry.get("Version", "?"),
            "license": (entry.get("License") or "").strip(),
            "url": (entry.get("URL") or entry.get("LicenseFile") or "").strip(),
        }
    return out


def main() -> int:
    wanted = direct_requirement_names()
    licences = installed_licences()

    print(f"pyjab {version(SELF)} declares {len(wanted)} runtime dependency(ies):")
    missing = []
    checked = []
    refused = []
    for name in sorted(wanted):
        info = licences.get(name)
        if info is None:
            # A marker did not match this platform -- pywin32 on Linux, usually.
            missing.append(name)
            continue
        checked.append((name, info))
        text = info["license"]
        for marker in REFUSED:
            if marker.lower() in text.lower():
                refused.append((name, info, marker))
                break

    for name, info in checked:
        print(f"  {name} {info['version']}: {info['license'] or '(not stated)'}")
    for name in missing:
        print(f"  {name}: not installed on this platform, skipped")

    if refused:
        print(f"\nFAILED: {len(refused)} dependency(ies) under a licence to avoid:")
        for name, info, marker in refused:
            print(f"  - {name} {info['version']}: {info['license']} (matched {marker!r})")
            if info["url"]:
                print(f"      {info['url']}")
        print(
            "\n  pyjab is being moved off the GPLv2 it inherited. A dependency under\n"
            "  one of these either blocks that or imposes its terms on everyone who\n"
            "  installs pyjab. Find a permissively licensed alternative, make it\n"
            "  optional, or raise it in an issue before adding it."
        )
        return 1

    print("\nPASSED: every runtime dependency is permissively licensed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
