"""The DCO check: parsing sign-offs, and matching them to a commit's people.

The check runs in CI on pull requests.  What is worth testing here is the part
that decides, plus the git plumbing -- the first version of the verification I ran
by hand made two commits straight to master because a branch name starting with a
slash was rejected and the fallback was read as a path.  A test that builds its own
repository cannot do that to anyone.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_dco", REPO_ROOT / "tools" / "check_dco.py"
)
dco = importlib.util.module_from_spec(_spec)
sys.modules["check_dco"] = dco
_spec.loader.exec_module(dco)


def commit(author="Gary Gao", author_email="gaozhao89@qq.com",
           committer=None, committer_email=None, parents=("x",), body=""):
    """A commit dict shaped like the one :func:`dco.describe` returns."""
    return {
        "sha": "0" * 40,
        "author": author,
        "author_email": author_email,
        "committer": committer or author,
        "committer_email": committer_email or author_email,
        "parents": list(parents),
        "body": body,
    }


# ---------------------------------------------------------------------------
# Reading the trailer
# ---------------------------------------------------------------------------

def test_a_sign_off_is_read():
    assert dco.sign_offs(commit(body="Subject\n\nSigned-off-by: Gary Gao <g@x>")) == \
        ["Gary Gao <g@x>"]


def test_several_sign_offs_are_read():
    body = ("Subject\n\nSigned-off-by: A <a@x>\nSigned-off-by: B <b@x>")

    assert dco.sign_offs(commit(body=body)) == ["A <a@x>", "B <b@x>"]


@pytest.mark.parametrize("spelling", [
    "Signed-off-by: A <a@x>",
    "signed-off-by: A <a@x>",
    "SIGNED-OFF-BY: A <a@x>",
    "Signed-Off-By: A <a@x>",
    "Signed-off-by:A <a@x>",
])
def test_the_trailer_is_recognised_however_it_is_capitalised(spelling):
    """Git writes it one way; people type it several."""
    assert dco.sign_offs(commit(body="Subject\n\n" + spelling)) == ["A <a@x>"]


def test_text_that_merely_mentions_a_sign_off_is_not_one():
    """Only a line that *is* the trailer counts, not prose about it."""
    body = "Subject\n\nThis commit adds a Signed-off-by: check."

    assert dco.sign_offs(commit(body=body)) == []


def test_a_commit_with_no_message_has_no_sign_off():
    assert dco.sign_offs(commit(body="")) == []


# ---------------------------------------------------------------------------
# Matching it to somebody
# ---------------------------------------------------------------------------

def test_a_sign_off_naming_the_author_matches():
    assert dco.attributable_to(commit(), "Gary Gao <gaozhao89@qq.com>")


def test_a_sign_off_naming_only_the_email_matches():
    assert dco.attributable_to(commit(), "gaozhao89@qq.com")


def test_a_sign_off_naming_only_the_name_matches():
    assert dco.attributable_to(commit(), "Gary Gao")


def test_the_case_does_not_matter():
    assert dco.attributable_to(commit(), "GARY GAO")


def test_a_sign_off_naming_the_committer_matches():
    """A maintainer applying someone's patch commits it under their own name."""
    patch = commit(author="Someone Else", author_email="else@x",
                   committer="Gary Gao", committer_email="gaozhao89@qq.com")

    assert dco.attributable_to(patch, "Gary Gao <gaozhao89@qq.com>")


def test_a_sign_off_naming_a_stranger_does_not_match():
    assert not dco.attributable_to(commit(), "Someone Else <nobody@example.com>")


def test_an_empty_sign_off_matches_nobody():
    assert not dco.attributable_to(commit(), "")


# ---------------------------------------------------------------------------
# What is skipped, and why
# ---------------------------------------------------------------------------

def test_a_merge_commit_is_skipped():
    """It authors nothing, so there is nothing for it to certify."""
    assert dco.is_merge(commit(parents=("a", "b")))
    assert not dco.is_merge(commit(parents=("a",)))


@pytest.mark.parametrize("name", [
    "dependabot[bot]", "github-actions[bot]", "renovate-bot", "some_bot",
])
def test_a_bot_author_is_skipped(name):
    """A bot cannot make the certification, and dependabot's commits come from
    another project's release rather than from its own author."""
    assert dco.is_bot(commit(author=name))


def test_a_person_whose_name_merely_contains_bot_is_not_skipped():
    assert not dco.is_bot(commit(author="Botanist Jones"))


# ---------------------------------------------------------------------------
# The whole thing, against a repository this test builds
# ---------------------------------------------------------------------------

#: A throwaway repository inherits the machine's global git config, and three of
#: the things it can contain break committing in a repository that has no signing
#: key and no business running anybody's hooks:
#:
#: * ``commit.gpgsign = true`` -- common, and fatal here.  On a machine with it
#:   set, ``git commit`` fails with "cannot run gpg" / "failed to write commit
#:   object", which is how this was found: seven of these tests failed on Windows
#:   while CI stayed green, because CI has no such setting.
#: * ``core.hooksPath`` -- a global hooks directory would run arbitrary hooks on a
#:   test commit.
#: * ``commit.template`` -- would prefix the message and change what is asserted.
#:
#: Turning all three off locally is the difference between testing check_dco.py
#: and testing whichever machine happens to be running the suite.
GIT = [
    "git",
    "-c", "user.name=Probe",
    "-c", "user.email=probe@example.com",
    "-c", "commit.gpgsign=false",
    "-c", "core.hooksPath=",
    "-c", "commit.template=",
]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git, and show what it said when it fails.

    ``check=True`` with ``capture_output=True`` raises with the command in the
    message and nothing else -- so the one thing worth having, git's own
    explanation, is the one thing thrown away.  That is why the Windows failure
    above took a guess to explain rather than a reading.
    """
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {repo} with {result.returncode}\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result


def run_git(repo: Path, *args: str) -> None:
    git(repo, *args)


def make_repo(tmp_path: Path, scripts) -> Path:
    """A throwaway repository, so these tests can make commits safely."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    for message, sign in scripts:
        # -s belongs to `git commit`, so it goes after the subcommand along with
        # the other options; putting it before makes git reject the invocation.
        args = GIT[1:] + ["commit", "-q", "--allow-empty"] + \
            (["-s"] if sign else []) + ["-m", message]
        git(repo, *args)
    return repo


def run_check(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "check_dco.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def test_a_signed_commit_passes(tmp_path):
    repo = make_repo(tmp_path, [("a signed commit", True)])

    result = run_check(repo, "--commit", "HEAD")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED" in result.stdout


def test_an_unsigned_commit_fails(tmp_path):
    repo = make_repo(tmp_path, [("no sign-off", False)])

    result = run_check(repo, "--commit", "HEAD")

    assert result.returncode == 1
    assert "MISSING" in result.stdout
    assert "git commit -s" in result.stdout


def test_a_sign_off_naming_a_stranger_fails(tmp_path):
    repo = make_repo(tmp_path, [("stranger\n\nSigned-off-by: Nobody <no@x>", False)])

    result = run_check(repo, "--commit", "HEAD")

    assert result.returncode == 1
    assert "MISMATCH" in result.stdout


def test_a_range_is_checked_oldest_first(tmp_path):
    """Every commit in the range matters, and they read in order.

    Three commits, because a range of two needs a third to be relative to --
    ``HEAD~2`` does not exist in a repository with two commits, which is how the
    first version of this test failed rather than checking anything.
    """
    repo = make_repo(tmp_path, [("oldest", True), ("middle", False), ("newest", True)])

    result = run_check(repo, "--range", "HEAD~2..HEAD")

    assert result.returncode == 1
    assert "middle" in result.stdout
    assert result.stdout.index("middle") < result.stdout.index("newest")


def test_the_base_form_matches_a_range(tmp_path):
    repo = make_repo(tmp_path, [("oldest", True), ("one", True), ("two", True)])
    run_git(repo, "tag", "base", "HEAD~2")

    result = run_check(repo, "--base", "base")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "one" in result.stdout and "two" in result.stdout


def test_nothing_to_check_is_not_a_failure(tmp_path):
    """An empty range happens on a push that adds no commits of its own."""
    repo = make_repo(tmp_path, [("only", True)])

    result = run_check(repo, "--range", "HEAD..HEAD")

    assert result.returncode == 0
    assert "nothing to check" in result.stdout


def test_an_unresolvable_range_says_what_to_do_about_it(tmp_path):
    """The message a contributor sees, not a bare git error.

    A pull request from a fork keeps its commits in the fork, and every outside
    contribution pyjab has received arrived that way.  If the fetch of
    ``pull/<number>/head`` is skipped, the range will not resolve, and the person
    reading the output is the person whose pull request is being checked -- so it
    has to say what happened and where to look.
    """
    repo = make_repo(tmp_path, [("only", True)])

    result = run_check(repo, "--range", "deadbeef..HEAD")

    assert result.returncode == 1
    assert "could not resolve the range" in result.stdout
    assert "fork" in result.stdout
    assert "pull/<number>/head" in result.stdout
    # The git complaint is kept, labelled, because it is what makes the failure
    # diagnosable -- but it is no longer the whole of the output.
    assert "git said:" in result.stdout
    assert result.stdout.index("could not resolve") < result.stdout.index("git said:")
