"""The local-content guard.

`tools/check_no_local_content.py` scans every tracked file for local paths and
credentials. Two things about it are asserted here rather than hoped for.

**Every pattern has a negative control.** A pattern that matches too much is worse
than no pattern: it gets muted, and then it stops matching the real thing. The DSH
pattern is the example that actually happened -- a scan for `dsh` in the project's
own issues matched `net/http: TLS handshake timeout` (#211, #214), which is why the
shared string here is the word `handshake`.

**A trusted file is not a blind spot.** `.gitignore` and the local-only guard have
to name the local paths, so the path patterns are relaxed for them. They are still
scanned for credentials, and `test_naming_a_path_is_not_a_licence_to_carry_a_token`
is what keeps that from being a hole.

The failure path is exercised end to end against a throwaway repository, because a
scanner that cannot report anything has never been asked to.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_no_local_content as guard  # noqa: E402


def found(text: str, path: str = "some/module.py") -> list[str]:
    return guard.findings_in_text(text, path)


# ---------------------------------------------------------------------------
# Local paths: one case it must catch, one it must not
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line", [
    'HOME = "/Users/someone/projects"',
    "log = '/home/someone/.cache/x'",
    r"root = 'C:\\Users\\someone\\scoop\\apps'",
    'docs = "~/Library/Mobile Documents/com~apple~CloudDocs"',
    'backup = "/Volumes/iCloud Drive/notes"',
    'SESSIONS = Path.home() / "~/.dsh/sessions"',
    "config = .dsh/settings.json",
    'settings = "dsh.toml"',
])
def test_local_paths_are_found(line):
    assert found(line), line


@pytest.mark.parametrize("line", [
    "#!/usr/bin/env python3",
    "python = /usr/local/bin/python3",
    'The TLS handshake timed out, so the run is retried.',       # #211: 'dsh' in 'handshake'
    "path = 'C:\\\\Program Files\\\\Java\\\\jdk-21'",
    "asyncio.sleep(1)",
    "docs/README.md explains the published pages",
])
def test_ordinary_text_is_not_a_local_path(line):
    assert not found(line), line


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def test_a_private_key_is_found():
    # Built rather than written out, for the same reason as the token below: this file
    # is scanned too, and a literal header here is a finding in its own right. The
    # first version of this test *was* a literal and it passed locally -- because the
    # guard only looked at tracked files and this file was brand new. CI caught it on
    # an already-pushed commit, which is what the candidate set below now prevents.
    assert found("-----BEGIN " + "RSA PRIVATE KEY-----")


def test_a_github_token_is_found():
    # Built rather than written out: a literal token in this file would be one.
    assert found("token = 'ghp_" + "A" * 30 + "'")


def test_a_short_lookalike_is_not_a_token():
    assert not found("ghp_short")
    assert not found("github_pat_example")


def test_an_aws_key_id_is_found():
    assert found("aws_access_key_id = AKIA" + "A" * 16)


# ---------------------------------------------------------------------------
# Tracked paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    ".env",
    ".env.local",
    "deploy/secrets.yaml",
    "certs/server.pem",
    "keys/id_rsa",
    ".vscode/settings.json",
    ".agents/skills/pyjab-testing/SKILL.md",
    ".dsh/settings.json",
    "CLAUDE.md",
])
def test_a_local_or_secret_path_is_a_finding(path):
    assert guard.path_findings(path), path


@pytest.mark.parametrize("path", [
    ".env.example",
    ".env.sample",
    "docs/README.md",
    "tests/test_environment.py",
    "pyjab/common/states.py",
    "tools/check_no_local_content.py",
])
def test_an_ordinary_path_is_not_a_finding(path):
    assert not guard.path_findings(path), path


# ---------------------------------------------------------------------------
# The exemption is not a hole
# ---------------------------------------------------------------------------

def test_naming_a_path_is_not_a_licence_to_carry_a_token():
    """The two-tier rule, which is the point of `MAY_NAME_LOCAL_THINGS`.

    `.gitignore` has to name `~/.dsh`, and the local-only guard has to list it.
    Relaxing the path patterns for those files must not stop them being scanned
    for credentials -- otherwise "this file is allowed to mention a local path"
    quietly becomes "this file is trusted".
    """
    trusted = "tools/check_local_only_files.py"
    assert trusted in guard.MAY_NAME_LOCAL_THINGS

    assert guard.findings_in_text('    "docs/TRIAGE.md",', trusted) == []
    assert guard.findings_in_text("token = 'ghp_" + "B" * 30 + "'", trusted)


def test_an_untrusted_file_is_scanned_for_both():
    assert guard.findings_in_text('x = "/Users/someone/y"', "pyjab/config.py")
    assert guard.findings_in_text("token = 'ghp_" + "C" * 30 + "'", "pyjab/config.py")


# ---------------------------------------------------------------------------
# End to end: it passes here, and it fails there
# ---------------------------------------------------------------------------

def test_the_checkout_is_clean():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_no_local_content.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED" in result.stdout


def test_a_planted_leak_makes_it_fail(tmp_path):
    """The failure path, in a repository built for the purpose.

    `/Users/someone` is deliberate: it is the shape of the leak this guard exists
    for, and the assertion is on the exit code and the file name rather than on
    the message, so rewording the output does not break the test.
    """
    repo = tmp_path / "leaky"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "settings.py").write_text(
        'CACHE = "/Users/someone/.cache/pyjab"\n', encoding="utf-8",
    )
    subprocess.run(["git", "add", "settings.py"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_no_local_content.py"),
         "--root", str(repo)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "settings.py" in result.stdout
    assert "FAILED" in result.stdout


def test_a_leak_is_found_before_it_is_even_added(tmp_path):
    """The candidate set, which is the reason this guard is worth running locally.

    A `git ls-files`-only guard cannot see a file that has not been added yet, so it
    passes on the machine where the leak is still cheap to fix and fails in CI on a
    commit that is already pushed. That is not hypothetical: it is what this tool's
    own test file did, with a literal private-key header in it.
    """
    repo = tmp_path / "unadded"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "notes.py").write_text('P = "/Users/someone/notes"\n', encoding="utf-8")
    # Deliberately NOT `git add`-ed.
    assert subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip() == ""

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_no_local_content.py"),
         "--root", str(repo)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "notes.py" in result.stdout


def test_a_clean_repository_passes(tmp_path):
    """The control for the test above: the same setup without the leak."""
    repo = tmp_path / "clean"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "settings.py").write_text('CACHE = "/tmp/pyjab"\n', encoding="utf-8")
    subprocess.run(["git", "add", "settings.py"], cwd=repo, check=True)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_no_local_content.py"),
         "--root", str(repo)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASSED" in result.stdout
