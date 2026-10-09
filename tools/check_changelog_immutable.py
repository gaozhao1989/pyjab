#!/usr/bin/env python3
"""A released changelog section must never change again.

Section 1.3 of AGENTS.md says released versions are immutable, and that has been
read as being about PyPI -- which it is, but the changelog is published too, inside
the sdist. The two can disagree, and one of them is the only one a reader of the
repository will ever see.

That happened at 1.6.3. Every entry added after the tag went into the 1.6.3 section,
because that section sits at the top of the file and the anchor used to insert them
matched it. The repository then claimed 1.6.3 included the DPI fix, the xpath leak
fix and the rest, while the sdist on PyPI -- built from the tree at the tag -- did
not. Nothing failed; it was noticed by hand, at the next release, which is not a
mechanism.

Why a recorded hash rather than a comparison against the tag
------------------------------------------------------------

Comparing a section to its tag is the obvious check and it does not work where the
check has to run. GitHub Actions checks out at depth 1: no tags, no history beyond
the one commit. `check_dco.py` skips itself for exactly this reason, which means the
thing it guards is unguarded in CI.

So the expected value is recorded in `tools/released_changelog_sections.json`, in the
tree, and compared against the working copy. No history is needed, no network, and it
fails on precisely one thing: a released section whose text has changed since it was
recorded.

Keeping it current
------------------

After tagging a release, extend the record:

    $ python tools/check_changelog_immutable.py --record 1.7.0

That reads the section out of the **tag**, not the working copy, so what gets frozen
is what shipped. `--record` refuses a version with no tag, refuses one already
recorded to a different value, and refuses a section it cannot find.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.rst"
RECORD = REPO_ROOT / "tools" / "released_changelog_sections.json"

#: `1.2.3 (2026-01-01)` on its own line, with the underline beneath it.
HEADING = re.compile(r"(?m)^(\d+\.\d+\.\d+) \(\d{4}-\d{2}-\d{2}\)\n-{2,}\n")


def sections(text: str) -> dict:
    """Every released section, keyed by version, as its text.

    The section runs to the next release heading, so it carries its own subsections
    and bullets. Trailing blank lines are dropped because they are not part of what
    a reader sees and would make the hash depend on how the file happens to end.
    """
    found = {}
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found[match.group(1)] = text[match.start():end].rstrip()
    return found


def digest(section: str) -> str:
    return "sha256:" + hashlib.sha256(section.encode("utf-8")).hexdigest()


def load_record() -> dict:
    if not RECORD.exists():
        return {}
    return json.loads(RECORD.read_text(encoding="utf-8"))


def save_record(record: dict) -> None:
    RECORD.write_text(
        json.dumps(dict(sorted(record.items())), indent=2) + "\n", encoding="utf-8"
    )


def tag_section(version: str) -> str:
    """The section as it is in the tag, which is what shipped."""
    tag = f"v{version}"
    result = subprocess.run(
        ["git", "show", f"{tag}:CHANGELOG.rst"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"no tag {tag}, or no CHANGELOG.rst in it")
    found = sections(result.stdout).get(version)
    if found is None:
        raise SystemExit(f"{tag} has no {version} section in its CHANGELOG")
    return found


def check() -> int:
    record = load_record()
    current = sections(CHANGELOG.read_text(encoding="utf-8"))
    failures = 0

    print(f"released sections recorded: {len(record)}")
    for version in sorted(record, key=lambda v: [int(p) for p in v.split(".")]):
        if version not in current:
            print(f"  {version}: section is MISSING from CHANGELOG.rst")
            failures += 1
        elif digest(current[version]) != record[version]:
            print(f"  {version}: section has CHANGED since it was released")
            failures += 1

    # Not a failure. Four older releases have a section here that their tag does not:
    # the `X.Y.Z (date)` heading arrived after 1.3.0, so their sdists carried a
    # changelog with no such section in it, and the ones in this file are
    # retrospective. There is nothing to compare those against and nothing to fix --
    # but the gap should be visible rather than silently passed over.
    for version in sorted(current, key=lambda v: [int(p) for p in v.split(".")]):
        if version not in record:
            print(f"  {version}: section here, none in its tag "
                  f"(predates the heading format) -- not checked")

    if failures:
        print(
            f"\nFAILED: {failures} released section(s) are not what shipped.\n"
            "\n  A released version's changelog is published in its sdist. Editing the\n"
            "  section afterwards makes the repository describe a release that never\n"
            "  happened, and the sdist is the only other copy -- so the two disagree\n"
            "  and nothing says which is right.\n"
            "\n  New entries belong under the next version. If the section genuinely\n"
            "  must change, say why in the commit that does it and update the record\n"
            "  in the same commit, so the change is deliberate and visible."
        )
        return 1

    print("\nPASSED: every recorded released section is unchanged.")
    return 0


def record(version: str) -> int:
    record_file = load_record()
    section = tag_section(version)
    value = digest(section)
    existing = record_file.get(version)
    if existing and existing != value:
        raise SystemExit(
            f"{version} is already recorded as {existing}; refusing to overwrite it "
            f"with {value}. A released section is not supposed to change."
        )
    record_file[version] = value
    save_record(record_file)
    print(f"recorded {version} from v{version}: {value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", metavar="VERSION",
                        help="freeze the section for VERSION, read from its tag")
    args = parser.parse_args()
    if args.record:
        return record(args.record)
    return check()


if __name__ == "__main__":
    sys.exit(main())
