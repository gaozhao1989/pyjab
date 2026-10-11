"""The two hand-maintained release records must name the version that shipped.

An hour after 1.11.1 was published, ``docs/7-Changelog.md`` -- the release history
published to the GitHub wiki -- was still topped by 1.11.0, while
``pyjab/__init__.py`` and ``CHANGELOG.rst`` both said 1.11.1.  Nothing failed; it was
noticed by hand.  The evidence is in the tag: at ``v1.11.1``,
``git show v1.11.1:docs/7-Changelog.md`` tops out at 1.11.0.

Why this placement matters
--------------------------

``release.yml`` runs the portable suite in the ``build`` job, and ``publish-pypi``
``needs: build``.  A test here therefore fails the release **before** anything reaches
PyPI -- which is the only point at which a wrong release record is still cheap to fix,
because a published version can never be edited or unpublished (AGENTS.md 1.3).

Version truth is ``pyjab.__version__``.  These two files are hand-maintained copies of
it and are exactly the ones that drift, so the check is mechanical: read the version,
and compare it to the newest dated section of CHANGELOG.rst and to the first row of the
table in docs/7-Changelog.md.

Nothing here reads Python source; this is about two published records, not about the
shape of the code (the ``pyjab-testing`` skill's rule 8 is about the latter).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

import pyjab

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_RST = REPO_ROOT / "CHANGELOG.rst"
DOCS_CHANGELOG_MD = REPO_ROOT / "docs" / "7-Changelog.md"


def _load_changelog_parser():
    """The repository's own reader for a released CHANGELOG.rst section.

    Reused rather than re-derived: its ``HEADING`` is the one definition of what a
    released section looks like, and it requires a date, so an ``Unreleased`` heading
    sitting above the newest release is skipped rather than counted.
    """
    spec = importlib.util.spec_from_file_location(
        "check_changelog_immutable", REPO_ROOT / "tools" / "check_changelog_immutable.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


changelog_parser = _load_changelog_parser()

#: The version cell of a release-history row, e.g. ``| **1.11.1** | ... |``.
RELEASE_ROW = re.compile(r"^\|\s*\*\*(\d+\.\d+\.\d+)\*\*\s*\|")


def newest_released_version(changelog_text: str) -> str | None:
    """The version of the topmost dated section, or None if there is none.

    ``sections()`` returns a dict built by walking the file front to back, so the first
    key is the section nearest the top.
    """
    found = changelog_parser.sections(changelog_text)
    return next(iter(found), None)


def first_release_row_version(markdown_text: str) -> str | None:
    """The version in the first row of the release-history table, or None."""
    for line in markdown_text.splitlines():
        match = RELEASE_ROW.match(line)
        if match:
            return match.group(1)
    return None


# ---------------------------------------------------------------------------
# The reading, which is the half that can be tested without the two files
# ---------------------------------------------------------------------------

def test_an_unreleased_heading_is_not_the_newest_release():
    """An Unreleased section may sit above the newest release; it is not a version."""
    text = (
        "Unreleased\n"
        "----------\n"
        "\n"
        "* work in progress\n"
        "\n"
        "1.2.0 - 2026-02-02\n"
        "------------------\n"
        "\n"
        "* a thing\n"
        "\n"
        "1.1.0 (2026-01-01)\n"
        "------------------\n"
        "\n"
        "* an older thing\n"
    )

    assert newest_released_version(text) == "1.2.0"


def test_the_oldest_release_is_still_a_release():
    """Both date separators in the file's history have to be readable."""
    text = "1.1.0 (2026-01-01)\n------------------\n\n* an older thing\n"

    assert newest_released_version(text) == "1.1.0"


def test_the_first_table_row_is_the_newest_release():
    text = (
        "| Version | What it was about |\n"
        "|---|---|\n"
        "| **1.2.0** | the new one |\n"
        "| **1.1.0** | the old one |\n"
    )

    assert first_release_row_version(text) == "1.2.0"


# ---------------------------------------------------------------------------
# The records themselves
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path, reader",
    [
        pytest.param(CHANGELOG_RST, newest_released_version, id="CHANGELOG.rst"),
        pytest.param(DOCS_CHANGELOG_MD, first_release_row_version, id="docs/7-Changelog.md"),
    ],
)
def test_the_newest_release_record_names_the_shipped_version(path, reader):
    text = path.read_text(encoding="utf-8")
    recorded = reader(text)

    assert recorded is not None, (
        f"{path.relative_to(REPO_ROOT)} has no release record this test can read, so "
        "it can no longer tell whether the file names the shipped version"
    )
    assert recorded == pyjab.__version__, (
        f"pyjab.__version__ is {pyjab.__version__} but the newest release record in "
        f"{path.relative_to(REPO_ROOT)} is {recorded}. A release cannot go out with the "
        "two records disagreeing"
    )
