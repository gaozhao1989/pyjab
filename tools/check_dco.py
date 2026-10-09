#!/usr/bin/env python
"""Check that commits carry the sign-off CONTRIBUTING.rst asks for.

Why this exists
---------------
``CONTRIBUTING.rst`` asks a contributor to sign off their commits: the Developer
Certificate of Origin, plus a grant that lets the maintainer distribute the
contribution under a licence other than the one in force.  That second half is
what stops the project being locked to GPLv2 forever by its own history.

A requirement nobody checks prevents nothing.  The first unsigned pull request
merges, its author has granted nothing, and the problem is exactly where it
started -- except that now it is in a commit rather than in a contributor's
silence.  This is the check.

What it verifies
----------------
For every commit in the range, that a ``Signed-off-by:`` trailer is present, and
that it names somebody the commit is actually attributable to -- the author or
the committer.  A sign-off line is a statement by a person that they had the
right to send the patch; one naming nobody involved states nothing.

Merge commits and bots are skipped, for reasons given at the code.

Usage
-----
    python tools/check_dco.py --base origin/master
    python tools/check_dco.py --range v1.5.0..HEAD
    python tools/check_dco.py --commit HEAD
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

#: A sign-off trailer, as git writes it with `git commit -s`.
SIGN_OFF = re.compile(r"^Signed-off-by:\s*(?P<who>.+?)\s*$", re.IGNORECASE | re.MULTILINE)

#: Accounts whose commits cannot certify anything, because there is no person
#: behind them to make the statement.  Dependabot's commits are generated from a
#: dependency's own release, and the right to submit that code belongs to that
#: project, not to the bot -- so requiring a sign-off would fail every one of
#: them and prove nothing.  It does mean a bot pull request deserves a read
#: rather than a rubber stamp, which is the trade being made here.
BOT_SUFFIXES = ("[bot]", "-bot", "_bot")

#: The commit that introduced this check, and therefore the point from which the
#: requirement applies.
#:
#: ``CONTRIBUTING.rst`` tells a contributor to run this against their own branch,
#: but the obvious way to try it is ``--base v1.5.0`` or similar on ``master`` --
#: where it reported nine commits as missing a sign-off.  Those nine are all
#: commits the maintainer pushed directly, before this file existed.  Nothing was
#: wrong with them and nothing could be: the rule did not exist yet, and a
#: requirement cannot be retroactive to commits made in its absence.
#:
#: Reporting them as failures was therefore wrong in a way that mattered -- it
#: made the documented command look broken to exactly the person being asked to
#: trust it, and it obscured the real signal, which is that every commit after
#: this one does carry a sign-off.
#:
#: If this commit is not an ancestor of the range being checked -- a fork branch,
#: an unrelated clone -- nothing is exempt and every commit is checked.  Failing
#: open is the right direction: the cost of a false exemption is that an unsigned
#: commit goes unremarked, and the cost of a false failure is that people stop
#: running the check.
REQUIRED_FROM = "350c9787eb57f41b72aee5e71f24e8c672b8b301"


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def commits_in(revision_range: str) -> list:
    """The commit hashes in a revision range, oldest first.

    A range that will not resolve is reported as such rather than as a bare git
    error, because the person reading the output is usually the person whose pull
    request is being checked, and the cause is always the same: one end of the
    range was never fetched.  A pull request from a fork keeps its commits in the
    fork, and every outside contribution to pyjab has arrived that way.
    """
    result = subprocess.run(["git", "rev-list", "--reverse", revision_range],
                            capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        print(f"could not resolve the range {revision_range}\n")
        if detail:
            print(f"  git said: {detail[0]}\n")
        print("  Both ends of the range have to be present in this checkout.")
        print("  A pull request from a fork keeps its commits in the fork, so the")
        print("  workflow fetches `pull/<number>/head` before running this check.")
        print("  If that step was skipped or failed, no commit can be checked --")
        print("  and since every outside contribution comes from a fork, the fetch")
        print("  is worth fixing rather than the check being run without it.")
        sys.exit(1)

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def describe(sha: str) -> dict:
    """The parts of a commit this check needs.

    The separators are ASCII unit/record separators because a commit message can
    contain anything, including newlines and the characters one would reach for
    first.
    """
    raw = git("show", "-s", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%P%x1f%B", sha)
    sha_out, author, author_email, committer, committer_email, parents, body = \
        raw.split("\x1f", 6)

    return {
        "sha": sha_out.strip(),
        "author": author.strip(),
        "author_email": author_email.strip(),
        "committer": committer.strip(),
        "committer_email": committer_email.strip(),
        "parents": parents.split(),
        "body": body,
    }


def is_merge(commit: dict) -> bool:
    """A merge commit authors nothing, so there is nothing for it to certify."""
    return len(commit["parents"]) > 1


def is_bot(commit: dict) -> bool:
    name = commit["author"].lower()
    return any(name.endswith(suffix) for suffix in BOT_SUFFIXES)


def before_the_rule(sha: str) -> bool:
    """Whether *sha* was committed before the requirement existed.

    Exact rather than a date comparison: the boundary is a commit, and asking git
    whether this one is an ancestor of it is the same question stated directly.
    A commit equal to the boundary is not exempt -- it is the one that introduced
    the rule.
    """
    # subprocess rather than the module's git(): that helper exits the process on
    # failure, and "the baseline is not in this clone" is an ordinary answer here
    # -- it is what happens when the check runs against a throwaway test
    # repository, or a fork that does not contain upstream history.
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", REQUIRED_FROM + "^{commit}"],
        capture_output=True, text=True,
    ).stdout.strip()
    if not resolved:
        # The baseline is not here, so nothing is exempt.  Failing open is the
        # right direction -- see REQUIRED_FROM.
        return False
    if sha == resolved:
        return False
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, resolved],
        capture_output=True,
    ).returncode == 0


def sign_offs(commit: dict) -> list:
    """Every name in a Signed-off-by trailer."""
    return [match.group("who").strip() for match in SIGN_OFF.finditer(commit["body"])]


def attributable_to(commit: dict, who: str) -> bool:
    """Whether a sign-off names the author or the committer of this commit.

    Compared loosely and in both directions, because the same person writes their
    name differently in git config and in a trailer -- "Gary Gao" against
    "garygao", or an address on one side only.

    An empty sign-off is rejected first, and has to be: the empty string is a
    substring of everything, so the bidirectional test below would match it
    against any author at all. A bare ``Signed-off-by:`` line would otherwise
    pass this check while certifying nothing.
    """
    who_lower = who.strip().lower()
    if not who_lower:
        return False
    for field in ("author", "committer"):
        name = commit[field].lower()
        email = commit[field + "_email"].lower()
        if name and (name in who_lower or who_lower in name):
            return True
        if email and email in who_lower:
            return True
    return False


def first_line(commit: dict) -> str:
    for line in commit["body"].splitlines():
        if line.strip():
            return line.strip()
    return "(no message)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None,
                        help="check BASE..HEAD, e.g. --base origin/master")
    parser.add_argument("--range", dest="revision_range", default=None,
                        help="an explicit git revision range")
    parser.add_argument("--commit", default=None,
                        help="check a single commit")
    args = parser.parse_args()

    if args.commit:
        revision_range = "-1 " + args.commit
        shas = [git("rev-parse", args.commit).strip()]
    elif args.revision_range:
        shas = commits_in(args.revision_range)
        revision_range = args.revision_range
    elif args.base:
        revision_range = f"{args.base}..HEAD"
        shas = commits_in(revision_range)
    else:
        parser.error("give one of --base, --range or --commit")

    if not shas:
        print(f"nothing to check in {revision_range}")
        return 0

    print(f"checking {len(shas)} commit(s) in {revision_range}\n")

    unsigned = []
    misattributed = []
    skipped = 0
    before_rule = 0

    for sha in shas:
        commit = describe(sha)
        short = commit["sha"][:8]
        label = first_line(commit)[:58]

        if before_the_rule(commit["sha"]):
            print(f"  {short}  before-rule  {label}")
            before_rule += 1
            continue
        if is_merge(commit):
            print(f"  {short}  skipped  merge commit")
            skipped += 1
            continue
        if is_bot(commit):
            print(f"  {short}  skipped  bot author ({commit['author']})")
            skipped += 1
            continue

        names = sign_offs(commit)
        if not names:
            print(f"  {short}  MISSING  {label}")
            unsigned.append(commit)
            continue
        if not any(attributable_to(commit, name) for name in names):
            print(f"  {short}  MISMATCH {label}")
            print(f"            signed off by {names}, authored by "
                  f"{commit['author']} <{commit['author_email']}>")
            misattributed.append(commit)
            continue

        print(f"  {short}  ok       {label}")

    if unsigned or misattributed:
        print()
        if unsigned:
            print(f"FAILED: {len(unsigned)} commit(s) without a sign-off:")
            for commit in unsigned:
                print(f"  - {commit['sha'][:8]} {first_line(commit)[:60]}")
        if misattributed:
            print(f"FAILED: {len(misattributed)} sign-off(s) naming nobody involved:")
            for commit in misattributed:
                print(f"  - {commit['sha'][:8]} {sign_offs(commit)} "
                      f"vs {commit['author']}")
        print(
            "\n  CONTRIBUTING.rst asks for `git commit -s`, which appends:\n"
            "\n      Signed-off-by: Your Name <you@example.com>\n"
            "\n  It certifies that you wrote the patch, or have the right to send\n"
            "  it, and grants the maintainer the right to distribute it under a\n"
            "  licence other than the current one. Without the second part the\n"
            "  project cannot be relicensed by anyone's decision -- only by\n"
            "  everyone's, for ever.\n"
            "\n  To fix the commits you have not pushed yet:\n"
            "\n      git rebase --signoff <base>\n"
        )
        return 1

    print(f"\nPASSED: every commit carries a sign-off "
          f"({skipped} skipped as merge or bot)")
    if before_rule:
        # Said plainly, because a reader who reached back past the rule needs to
        # know these were not quietly ignored.
        print(f"\n  {before_rule} commit(s) marked before-rule: they predate "
              f"{REQUIRED_FROM[:8]},\n"
              "  the commit that introduced this check.  A requirement cannot "
              "apply to\n"
              "  commits made before it existed, so they are reported rather "
              "than failed.\n"
              "  Every commit after that one is checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
