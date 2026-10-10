"""How this project is actually worked on, measured from the session transcripts.

Written because the same three facts had to be re-derived by hand three times, and
one of them was got wrong twice. The transcript is a `jsonl.zstd` per session under
`~/.dsh/sessions/<slugified-workspace>/`, and the shape is not what it looks like:

* a call is ``{"type": "tool/call", "data": {"name": ..., "arguments": ...}}`` --
  **the tool name is `data.name`, not `data.toolName`.** Looking for `toolName`
  counts every call and names none of them, which reads as "4919 calls, (none)".
* a `skill` call's arguments are a JSON *string*, so the skill's name needs a second
  parse.

The measurement that matters is `skill`: it is the difference between rules that live
in files and rules that live in somebody's memory. This project measured 40 of 4921
(0.81%) -- all six skills loaded at least once, so the failure was never "they are
ignored", it was "not loaded at the moment they would have changed the work".

Usage:
    python tools/session_metrics.py
    python tools/session_metrics.py --since-minutes 90
    python tools/session_metrics.py --json
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
import time
from pathlib import Path

SESSIONS = Path.home() / ".dsh" / "sessions"

#: The skills this repository ships. Named so that "never loaded" is a visible
#: zero rather than an absence -- an absence looks the same as a typo.
EXPECTED_SKILLS = (
    "pyjab-release",
    "pyjab-testing",
    "pyjab-jab-bindings",
    "pyjab-docs-wiki",
    "pyjab-issue-triage",
    "pyjab-dev-environment",
)


def workspace_session_dirs(workspace: Path) -> list[Path]:
    """The session directories belonging to *workspace*.

    The slug is not reproduced here on purpose. It replaces separators and encodes
    characters in a way that took three attempts to guess (`~0020` for a space,
    `~007E` for a tilde, and the leading separator doubled) -- so this searches
    instead, keyed on the workspace's own directory name, which survives slugging.
    """
    if not SESSIONS.is_dir():
        return []
    # The slug ends with the workspace's own directory name. Matching on a
    # substring instead also catches a *sibling* project whose name starts the
    # same way -- `pyjab` matched this machine's `pyjab-mcp` workspace too, and
    # reported 7790 calls where this project has 4921.
    suffix = "-" + workspace.name + "--"
    return sorted(p for p in SESSIONS.iterdir() if p.is_dir() and p.name.endswith(suffix))


def session_files(dirs: list[Path], since: float | None) -> list[Path]:
    found: list[Path] = []
    for directory in dirs:
        for path in directory.rglob("session.v4.jsonl.zstd"):
            if since is None or path.stat().st_mtime >= since:
                found.append(path)
    return sorted(found)


def read_transcript(path: Path):
    """Yield each JSON row of a compressed session transcript."""
    try:
        raw = subprocess.run(
            ["zstd", "-d", "-c", str(path)], capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for line in raw.splitlines():
        try:
            yield json.loads(line)
        except Exception:
            continue


def collect(files: list[Path]) -> tuple[collections.Counter, collections.Counter, int]:
    tools: collections.Counter = collections.Counter()
    skills: collections.Counter = collections.Counter()
    calls = 0
    for path in files:
        for row in read_transcript(path):
            if row.get("type") != "tool/call":
                continue
            data = row.get("data") or {}
            name = data.get("name") or "(unnamed)"
            tools[name] += 1
            calls += 1
            if name == "skill":
                try:
                    invoked = json.loads(data.get("arguments") or "{}").get("name")
                except Exception:
                    invoked = None
                skills[invoked or "(unparsed)"] += 1
    return tools, skills, calls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--since-minutes", type=float, default=None,
                        help="only transcripts modified in the last N minutes")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    since = None if args.since_minutes is None else time.time() - args.since_minutes * 60
    dirs = workspace_session_dirs(args.workspace.resolve())
    files = session_files(dirs, since)
    tools, skills, calls = collect(files)

    if args.json:
        print(json.dumps({
            "sessions": [str(p) for p in files],
            "calls": calls,
            "tools": dict(tools.most_common()),
            "skills": dict(skills.most_common()),
        }, indent=2))
        return 0

    print(f"session directories : {len(dirs)}")
    print(f"transcripts read    : {len(files)}"
          + (f"  (modified in the last {args.since_minutes:g} min)" if since else ""))
    if not calls:
        print()
        print("No tool calls found. Check --workspace and that zstd is installed.")
        return 0

    print(f"tool calls          : {calls}")
    print()
    print("what it is spent on")
    print("-------------------")
    for name, count in tools.most_common(12):
        share = count * 100.0 / calls
        print(f"  {name:<18} {count:>6}  {share:5.1f}%  {'#' * int(share / 2)}")

    loaded = sum(skills.values())
    print()
    print("skills loaded")
    print("-------------")
    print(f"  {loaded} of {calls} calls ({loaded * 100.0 / calls:.2f}%)")
    for name in EXPECTED_SKILLS:
        count = skills.get(name, 0)
        mark = "ok  " if count else "NEVER"
        print(f"  {mark} {name:<24} {count}")
    unexpected = {k: v for k, v in skills.items() if k not in EXPECTED_SKILLS}
    for name, count in sorted(unexpected.items()):
        print(f"  note {name:<24} {count}  (not one of this project's skills)")

    never = [s for s in EXPECTED_SKILLS if not skills.get(s)]
    if never:
        print()
        print(f"NOTE: never loaded: {', '.join(never)}")
    if calls and loaded * 100.0 / calls < 1.0:
        print()
        print("NOTE: under 1% of calls load a skill. See AGENTS.md 7.1 -- the rule is that")
        print("      a dispatch names the skills to load, because the failure is timing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
