"""No tracked file may contain local, machine-specific or secret content.

The rule this enforces, in the maintainer's words:

> Nothing local goes into Git. Local documents, the working environment's own
> configuration, anything that only makes sense on one machine -- none of it is
> published, in a file, in an issue, or anywhere else.

`tools/check_local_only_files.py` covers a *list* of known local files. This covers
the two things a list cannot:

* **paths that are local or secret by shape** -- an `.env`, a key file, an editor's
  project directory, the harness's config -- caught whether or not anyone remembered
  to add them to a list, and
* **content inside an ordinary tracked file** -- an absolute home path, an iCloud
  path, a token, a private key -- which is how machinery details actually escape:
  not as a whole file, but pasted into a script, a test, a workflow or a document.

Two things keep this from being a `grep` with opinions.

**The patterns need negative controls.** `/usr/bin` is not a home directory,
`handshake` is not a DSH reference, and a file that *describes* these patterns is
not leaking them. Those are tests, not hopes -- see `tests/test_no_local_content.py`,
where each pattern is exercised against a case it must **not** match as well as one
it must.

**Naming is not carrying.** `.gitignore` has to name every local path, and
`check_local_only_files.py` has to list them, or neither can do its job. Those files
are exempt from the *path* patterns and still scanned for credentials -- which is
the distinction `MAY_NAME_LOCAL_THINGS` draws, rather than the blunter "this file is
trusted", which would hide a token pasted into it tomorrow.

Usage:
    python tools/check_no_local_content.py             # every tracked file
    python tools/check_no_local_content.py --root DIR  # a different checkout
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Files whose job is to name local paths, so naming one is not a leak. They are
#: still scanned for every secret pattern below.
MAY_NAME_LOCAL_THINGS = frozenset({
    ".gitignore",
    "MANIFEST.in",
    "tools/check_local_only_files.py",
    "tools/check_no_local_content.py",
    "tests/test_no_local_content.py",
})

#: Local or machine-specific content, as a pattern and a description.
LOCAL_PATH_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"/(?:Users|home)/[A-Za-z0-9][A-Za-z0-9._-]*", "an absolute home directory"),
    (r"[A-Za-z]:\\\\?Users\\\\[^\\\s\"']+", "an absolute Windows home directory"),
    (r"Mobile Documents|iCloud Drive", "an iCloud path"),
    (r"~/\.dsh|\.dsh/|\bdsh\.(?:toml|json|ya?ml)\b", "the harness's local configuration"),
)

#: Credentials. These are the patterns no file is excused from.
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}", "a GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "a GitHub token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS key id"),
    (r"\bsk-[A-Za-z0-9]{20,}", "an API key"),
)

#: Tracked paths that should never be tracked, by pattern rather than by name.
#: `.env.example` and friends are deliberately not matched: an example is the one
#: form of these files that belongs in a repository.
PATH_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(^|/)\.env$|(^|/)\.env\.(?!example|sample|template)[A-Za-z0-9_.-]+$", "an environment file"),
    (r"(^|/)\.(?:netrc|npmrc|pypirc|git-credentials)$", "a credentials file"),
    (r"(^|/)(?:id_rsa|id_ed25519|id_ecdsa)(?:\.pub)?$|\.(?:pem|p12|pfx|key)$", "a key file"),
    (r"(^|/)(?:credentials|secrets?)\.(?:json|toml|ya?ml|ini)$", "a credentials file"),
    (r"(^|/)\.(?:dsh|claude|cursor|idea)(/|$)|(^|/)CLAUDE\.md$", "local tool configuration"),
    (r"(^|/)\.vscode(/|$)", "an editor's project directory"),
    (r"(^|/)\.agents(/|$)|(^|/)AGENTS\.local\.md$", "local agent configuration"),
)

_COMPILED_LOCAL = tuple((re.compile(p), what) for p, what in LOCAL_PATH_PATTERNS)
_COMPILED_SECRET = tuple((re.compile(p), what) for p, what in SECRET_PATTERNS)
_COMPILED_PATH = tuple((re.compile(p), what) for p, what in PATH_PATTERNS)


def path_findings(path: str) -> list[str]:
    """Whether a *tracked path* is local or secret by shape."""
    return [f"{path}: {what}" for pattern, what in _COMPILED_PATH if pattern.search(path)]


def patterns_for(path: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    """Which content patterns apply to *path*.

    Everything is checked for credentials. The path patterns are relaxed only for
    the files whose purpose is to name local paths.
    """
    if path in MAY_NAME_LOCAL_THINGS:
        return _COMPILED_SECRET
    return _COMPILED_LOCAL + _COMPILED_SECRET


def findings_in_text(text: str, path: str) -> list[str]:
    """Every line of *text* carrying local or secret content, as ``path:line``."""
    found: list[str] = []
    patterns = patterns_for(path)
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, what in patterns:
            match = pattern.search(line)
            if match:
                found.append(f"{path}:{number}: {what} -- {match.group(0)[:40]!r}")
    return found


def files_to_check(root: Path) -> list[str]:
    """Every file that would be committed: tracked, plus untracked and not ignored.

    `--others --exclude-standard` is load-bearing rather than thorough. A guard that
    only looks at `git ls-files` cannot warn about a file that has not been committed
    yet -- which is exactly when warning is cheap and when the file is still easy to
    change. The first version of *this tool's own test file* contained a literal
    private-key header; it was untracked at the time, so the guard passed locally and
    CI caught it on a commit that had already been pushed.
    """
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def scan(root: Path) -> list[str]:
    """Findings across every file in *root* that would be committed."""
    findings: list[str] = []
    for path in files_to_check(root):
        findings.extend(path_findings(path))
        try:
            text = (root / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # Not text, or gone from the working tree. The path rules applied.
            continue
        findings.extend(findings_in_text(text, path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO,
                        help="the checkout to scan (default: this one)")
    args = parser.parse_args()

    findings = scan(args.root)
    print(f"scanned {len(files_to_check(args.root))} files that would be committed in {args.root}")
    if findings:
        print()
        for finding in findings:
            print(f"LEAK: {finding}")
        print()
        print(f"FAILED: {len(findings)} local or secret item(s) in files that would be committed.")
        print()
        print("  Committed means in every clone and in the published history: deleting the")
        print("  file later does not remove it. Take the content out, and if it is a")
        print("  credential, rotate it -- removing it from the tip does not unsay it.")
        return 1
    print("PASSED: nothing that would be committed names a local path or carries a secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
