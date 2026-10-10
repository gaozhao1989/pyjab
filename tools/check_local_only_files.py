"""Local-only files must never reach a distribution.

There are two separate facts, and this guard checks both because they fail
independently:

1. **git ignores the path** -- so it is not in the repository.
2. **the sdist does not contain it** -- so it is not on PyPI either.

`.gitignore` does not protect the sdist. An sdist is built from the *working
tree*, so a file that git is happy to ignore is still sitting there when
setuptools walks it, and `MANIFEST.in` is the only thing that excludes it. The
maintainer notes in `docs/` appeared in this project's notes for exactly that
reason, and `.agents/` -- the skills and briefs this repository is worked on with
-- had no exclusion at all before this guard existed.

Verified by behaviour, not by declaration: `git check-ignore` decides the first
fact and the **built archive's own file list** decides the second. A guard that
only grepped `.gitignore` would pass while the package leaked.

Usage:
    python tools/check_local_only_files.py                  # builds an sdist
    python tools/check_local_only_files.py --sdist dist/x.tar.gz
    python tools/check_local_only_files.py --no-sdist       # only the git half
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Paths that are part of how this checkout is worked on and must never ship.
#: Kept as a literal rather than read out of `.gitignore`, because the point is
#: to compare two independent records -- a list derived from one of them could
#: not disagree with it. `test_every_path_is_also_named_in_gitignore` below
#: keeps the two in step.
LOCAL_PATHS = (
    "AGENTS.md",
    "AGENTS.local.md",
    ".agents",
    "docs/TRIAGE.md",
    "docs/ROADMAP.md",
    "docs/PYJAB_MCP_PLAN.md",
    "docs/VERIFY_M0_AND_SOAK.md",
    "docs/DEPENDENCY_ANALYSIS.md",
    "docs/MCP_ENABLING_PLAN.md",
    "docs/ISSUE_REPLIES.md",
    "docs/CONSENT_REQUESTS.md",
    "docs/replies",
)


def git_ignores(path: str) -> bool:
    """Whether git ignores *path*. Behaviour, not a pattern match."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=REPO, capture_output=True,
    )
    return result.returncode == 0


def build_sdist() -> Path | None:
    """Build an sdist into a temporary directory, or say why not."""
    out = Path(tempfile.mkdtemp(prefix="pyjab-sdist-"))
    try:
        subprocess.run(
            [sys.executable, "-m", "build", "--sdist", "--outdir", str(out)],
            cwd=REPO, capture_output=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  cannot build an sdist: {exc}")
        return None
    built = sorted(out.glob("*.tar.gz"))
    return built[0] if built else None


def sdist_members(sdist: Path) -> list[str]:
    """Every path inside *sdist*, with the leading ``<name>-<version>/`` removed."""
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
    roots = {n.split("/")[0] for n in names}
    root = sorted(roots)[0] if len(roots) == 1 else ""
    prefix = root + "/"
    return [n[len(prefix):] if n.startswith(prefix) else n for n in names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdist", type=Path, default=None,
                        help="an archive to inspect instead of building one")
    parser.add_argument("--no-sdist", action="store_true",
                        help="check only the git half")
    args = parser.parse_args()

    failures: list[str] = []

    print("git ignores them")
    print("----------------")
    for path in LOCAL_PATHS:
        ignored = git_ignores(path)
        print(f"  {'ok  ' if ignored else 'LEAK'} {path}")
        if not ignored:
            failures.append(f"git does not ignore {path!r}")

    # The two records must not drift: a path in one and not the other is how a
    # local note stops being local without anybody deciding that.
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    for path in LOCAL_PATHS:
        stem = "/" + path if path in {"AGENTS.md", "AGENTS.local.md"} else path
        if path not in gitignore and stem not in gitignore:
            failures.append(f"{path!r} is not named in .gitignore at all")

    if not args.no_sdist:
        sdist = args.sdist or build_sdist()
        print()
        print("the built archive does not contain them")
        print("--------------------------------------")
        if sdist is None:
            failures.append("no sdist to inspect (build failed)")
        else:
            print(f"  inspecting {sdist.name}")
            members = sdist_members(sdist)
            for path in LOCAL_PATHS:
                hit = [m for m in members if m == path or m.startswith(path.rstrip("/") + "/")]
                print(f"  {'ok  ' if not hit else 'LEAK'} {path}"
                      + (f"  -> {len(hit)} entr{'y' if len(hit) == 1 else 'ies'}" if hit else ""))
                if hit:
                    failures.append(f"{path!r} is inside the sdist ({hit[0]})")

    print()
    if failures:
        for problem in failures:
            print(f"FAILED: {problem}")
        return 1
    print("PASSED: every one is ignored by git and absent from the distribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
