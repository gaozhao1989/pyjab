"""Local-only files must never reach a distribution.

There are three separate facts, and this guard checks all three because they fail
independently:

1. **git ignores the path** -- so a new file at that path is not added by accident.
2. **git does not track the path** -- so it is not in the repository or in anyone's
   clone.
3. **the sdist does not contain it** -- so it is not on PyPI either.

`.gitignore` does not protect the sdist. An sdist is built from the *working
tree*, so a file that git is happy to ignore is still sitting there when
setuptools walks it, and `MANIFEST.in` is the only thing that excludes it. The
maintainer notes in `docs/` appeared in this project's notes for exactly that
reason, and `.agents/` -- the skills and briefs this repository is worked on with
-- had no exclusion at all before this guard existed.

**`.gitignore` does not protect the repository either, and fact 2 is why it is
here.** An ignore rule is advice to `git add`, not a lock: `git add -f` overrides
it, and after that the path is tracked, the ignore rule is irrelevant, and the
file is in every clone and in the published history for good. That is not
hypothetical. A set of maintainer notes was added that way, deleted in a later
commit, and is **still readable out of the history** -- deleting a tracked file
removes it from the tip, not from the repository, and nothing here will name the
commit or the paths, because a retrieval recipe in a published file is a worse
leak than the thing it is warning about.

Verified by behaviour, not by declaration: `git check-ignore` decides the first
fact, `git ls-files` the second, and the **built archive's own file list** the
third. A guard that only grepped `.gitignore` would pass while the package
leaked.

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

# The path patterns live in the other guard, so that there is one list of them and
# this file does not have to publish the names of the local configuration it keeps
# out. Imported by path because `tools/` is not a package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_no_local_content import path_findings  # noqa: E402

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
    "docs/MARKET_AND_COMPETITIVE_ANALYSIS.md",
    "docs/CONSENT_REQUESTS.md",
    "docs/replies",
)

#: Paths that are local or secret *by shape* rather than by name -- an `.env`, a key
#: file, the harness's own configuration -- and therefore must not ship either. The
#: patterns live in `tools/check_no_local_content.py` so that there is one list of
#: them, and so that this file does not have to publish the names of the local
#: configuration it is keeping out.


def git_ignores(path: str) -> bool:
    """Whether git ignores *path*. Behaviour, not a pattern match.

    **Both forms are tried, and that is load-bearing.** A pattern ending in a
    slash -- `/.agents/`, which is how this repository writes it -- matches
    **directories only**, and `git check-ignore` cannot tell that a path is a
    directory when the path is not there. In a fresh clone `.agents/` does not
    exist, so `git check-ignore .agents` reports "not ignored" while the
    directory would in fact be ignored the moment it appeared. CI is a fresh
    clone, which is how this was found: the guard failed there and passed here,
    where the directory happens to exist.

    A trailing slash is git's documented way to say "this is a directory", so
    testing the path both ways is correct for files and for directories, and it
    does not depend on the path existing.
    """
    for candidate in (path, path.rstrip("/") + "/"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=REPO, capture_output=True,
        )
        if result.returncode == 0:
            return True
    return False


def tracked_paths() -> set[str]:
    """Every path git tracks, i.e. every path in a clone of this repository.

    This is the fact `.gitignore` cannot give you. Once a local file has been
    force-added it is tracked, the ignore rule has no further effect, and no
    amount of deleting it later takes it out of the history.
    """
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


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

            # The same question for paths that are local by *shape* rather than by
            # name, so this file does not have to publish the names. A `.dsh` config
            # or an `.env` that reached the archive is a leak whether or not anyone
            # put it on a list.
            for member in members:
                for problem in path_findings(member):
                    print(f"  LEAK {problem}")
                    failures.append(f"{problem} is inside the sdist")

    # The fact that mattered most and was missing: a force-added local file is
    # tracked, and `.gitignore` has nothing to say about a tracked path. Every
    # local note this repository has ever leaked went out this way -- see the
    # module docstring.
    print()
    print("git does not track them")
    print("-----------------------")
    tracked = tracked_paths()
    for path in LOCAL_PATHS:
        hits = sorted(t for t in tracked
                      if t == path or t.startswith(path.rstrip("/") + "/"))
        print(f"  {'ok  ' if not hits else 'LEAK'} {path}"
              + (f"  -> tracked as {hits[0]}" if hits else ""))
        if hits:
            failures.append(
                f"{path!r} is tracked by git ({hits[0]}) -- deleting it does not "
                f"remove it from the history"
            )

    print()
    if failures:
        for problem in failures:
            print(f"FAILED: {problem}")
        return 1
    print("PASSED: every one is ignored by git, untracked, and absent from the distribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
