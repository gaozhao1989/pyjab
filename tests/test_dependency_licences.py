"""The dependency licence gate, without needing pip-licenses installed.

The gate itself runs in CI against a real install; what is worth checking here is
the part that decides, because a gate that quietly passes everything is worse
than no gate at all.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_dependency_licences",
    REPO_ROOT / "tools" / "check_dependency_licences.py",
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["check_dependency_licences"] = gate
_spec.loader.exec_module(gate)


def refuses(license_text: str) -> bool:
    """The same test main() applies, over one licence string."""
    return any(marker.lower() in license_text.lower() for marker in gate.REFUSED)


# ---------------------------------------------------------------------------
# What must be refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "GPL-2.0-only",
    "GPLv3",
    "GNU General Public License v2 (GPLv2)",
    "LGPL-2.1",
    "AGPL-3.0",
    "GNU Affero General Public License v3",
    "SSPL-1.0",
    "EUPL-1.2",
    "CDDL-1.0",
    "Sleepycat License",
    "CC-BY-SA-4.0",
    "Commons Clause",
])
def test_copyleft_is_refused(text):
    assert refuses(text)


# ---------------------------------------------------------------------------
# What must not be, or the gate blocks ordinary work
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "MIT",
    "MIT-CMU",
    "BSD-3-Clause",
    "Apache-2.0",
    "Apache Software License",
    "ISC",
    "PSF-2.0",
    "Python Software Foundation License",
    "Zope Public License",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "",
    "UNKNOWN",
])
def test_permissive_is_allowed(text):
    assert not refuses(text)


def test_the_project_itself_is_not_in_its_own_requirement_list():
    """pyjab is GPLv2; checking it against itself would always fail."""
    assert gate.SELF.lower() not in {n.lower() for n in gate.direct_requirement_names()}


def test_only_runtime_requirements_are_collected():
    """Extras are opt-in, so a dev-only dependency must not be gated."""
    names = gate.direct_requirement_names()

    assert names, "pyjab declares no runtime dependencies at all?"
    assert "pytest" not in names, "the dev extra leaked into the runtime list"


def test_requirement_names_are_normalised():
    """compare_underscores-to-dashes so a lookup by metadata name succeeds."""
    names = gate.direct_requirement_names()

    assert all("_" not in name for name in names)
    assert all(name == name.lower() for name in names)
