"""A released changelog section must not change.

The bug this exists for was found by hand at the 1.7.0 release: every entry added
after v1.6.3 went into the 1.6.3 section, because that section is at the top of the
file and the anchor used to insert them matched it. The repository then claimed
1.6.3 included the DPI fix and the xpath leak fix, while the sdist on PyPI -- built
from the tree at the tag -- did not.

There is no history in CI to compare against, so the expected values are recorded in
the tree. These tests are about the reading and the comparing, which is the half that
can be tested here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "check_changelog_immutable", REPO_ROOT / "tools" / "check_changelog_immutable.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = load_tool()

TWO_RELEASES = """\
CHANGELOG
=========

1.2.0 (2026-02-02)
------------------

Something new.

Added
~~~~~

* a thing

1.1.0 (2026-01-01)
------------------

Something older.

Fixed
~~~~~

* an older thing
"""


def test_it_finds_every_released_section():
    found = tool.sections(TWO_RELEASES)

    assert sorted(found) == ["1.1.0", "1.2.0"]
    assert "a thing" in found["1.2.0"]
    assert "an older thing" in found["1.1.0"]


def test_a_section_stops_at_the_next_release():
    """The whole bug: text leaking from one release into the one above it."""
    found = tool.sections(TWO_RELEASES)

    assert "an older thing" not in found["1.2.0"]
    assert "a thing" not in found["1.1.0"]


def test_the_digest_changes_when_the_section_does():
    before = tool.digest("1.2.0 (2026-02-02)\n------------------\n\n* a thing")
    after = tool.digest("1.2.0 (2026-02-02)\n------------------\n\n* a thing\n* and another")

    assert before != after


def test_trailing_blank_lines_do_not_count():
    """They are not something a reader sees, and would make the digest depend on
    how the file happens to end."""
    a = tool.sections("1.2.0 (2026-02-02)\n------------------\n\n* a thing\n")
    b = tool.sections("1.2.0 (2026-02-02)\n------------------\n\n* a thing\n\n\n")

    assert tool.digest(a["1.2.0"]) == tool.digest(b["1.2.0"])


def test_a_heading_without_a_date_is_not_a_release_section():
    """`Unreleased` is not a version, and neither is a bare number.

    The changelog had an `Unreleased` heading until 1.6.3; if the reader took it as
    a release it would be recorded and then fail for ever.
    """
    found = tool.sections("Unreleased\n----------\n\n* something\n\n1.2.0 (2026-02-02)\n------------------\n\n* a thing")

    assert sorted(found) == ["1.2.0"]


def test_the_record_is_a_file_in_the_tree():
    """Not history, not the network: CI checks out at depth 1 with no tags."""
    record = json.loads((REPO_ROOT / "tools" / "released_changelog_sections.json").read_text(encoding="utf-8"))

    assert record, "the record must not be empty"
    assert all(v.startswith("sha256:") for v in record.values())
    assert "1.7.0" in record, "the current release has to be recorded"


def test_every_recorded_version_is_in_the_changelog():
    current = tool.sections((REPO_ROOT / "CHANGELOG.rst").read_text(encoding="utf-8"))
    record = json.loads((REPO_ROOT / "tools" / "released_changelog_sections.json").read_text(encoding="utf-8"))

    missing = sorted(set(record) - set(current))

    assert not missing, f"recorded but absent from CHANGELOG.rst: {missing}"


def test_the_check_passes_on_the_repository():
    """End to end, which is what CI runs."""
    assert tool.check() == 0


# ---------------------------------------------------------------------------
# The workflow files, because a bad one fails with no jobs at all
# ---------------------------------------------------------------------------

def test_every_workflow_is_valid_yaml():
    """A CI that cannot start reports nothing useful.

    Adding the step above to ci.yml put `- name:` at four spaces where its
    neighbours use six. The run finished as a failure with **zero jobs** and no
    logs, and "This workflow run cannot be retried" -- which reads like
    infrastructure rather than a syntax error in a file that was just edited. It
    cost a round trip to find.

    PyYAML is a test dependency, so this is cheap to check before pushing.
    """
    yml = pytest.importorskip("yaml")
    workflows = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))

    assert workflows, "no workflow files found"
    for path in workflows:
        try:
            yml.safe_load(path.read_text(encoding="utf-8"))
        except yml.YAMLError as error:
            pytest.fail(f"{path.name} is not valid YAML: {error}")


def test_every_workflow_step_named_like_a_check_runs_something():
    """A step with a `name` and no `run`/`uses` does nothing and is invisible."""
    yml = pytest.importorskip("yaml")

    for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        document = yml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps", []):
                if "name" in step and "run" not in step and "uses" not in step:
                    pytest.fail(f"{path.name}:{job_name}: step {step['name']!r} does nothing")


def test_the_guard_is_wired_into_ci():
    """The check is worth nothing if nothing runs it."""
    yml = pytest.importorskip("yaml")

    document = yml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    runs = [s.get("run", "") for job in (document.get("jobs") or {}).values()
            for s in job.get("steps", [])]

    assert any("check_changelog_immutable.py" in r for r in runs), (
        "tools/check_changelog_immutable.py is not run by CI"
    )
