#!/usr/bin/env python
"""Dispatch one GUI task to GitHub, wait for it, and print what it measured.

Java UI tests run on GitHub and never here (AGENTS.md section 4). Following that rule by
hand means four commands, a guessed ``sleep``, and a job-name pattern that fails silently
-- issue #190:

    gh workflow run windows-gui.yml -f task=gui-suite
    sleep 40
    gh run list --workflow=windows-gui.yml --limit 3 --json databaseId --jq '.[0].databaseId'
    gh run watch <id>
    gh run view <id> --log | awk -F'\\t' '$2 ~ /task=gui-suite/ {print $3}'

Three things are wrong with that beyond the typing. The sleep is a guess: too short and the
run is not listed yet, too long and it is dead time. The awk matches on a *job name*, so a
renamed job matches nothing and prints nothing, which looks like "nothing to report". And
the grep at the end is written from memory each time, so two runs of the same question are
not comparable.

Usage
-----

    python tools/gui_run.py <task> [--java 8|11|17|21] [--artifact-file NAME]

    python tools/gui_run.py jvm-discovery
    python tools/gui_run.py m0 --artifact-file m0.json
    python tools/gui_run.py gui-suite --java 8 --timeout 3600

``<task>`` is validated against the ``options:`` list in
``.github/workflows/windows-gui.yml``, so a renamed task fails loudly here rather than
producing a dispatch that runs nothing.

Why the artifact rather than the run log
----------------------------------------

The workflow uploads ``*.log``, ``*.json``, ``*.txt`` and ``*.png`` under ``if: always()``,
with the comment "a failed GUI run is exactly when the measurement is worth reading". That
is the thing to read: the artifact is named ``windows-gui-<task>-jdk<java>``, its contents
are stable and comparable between runs, and reading it needs no dependency on a job's
display name.

A task's own log is usually ``<task>.log``; ``m0`` writes ``m0.json``, which is what
``--artifact-file`` is for. **With no ``--artifact-file``, every file in the artifact is
printed**, so the default needs no knowledge of any one task's filename.

Choosing which run is yours
----------------------------

``gh workflow run`` returns no run id, and its only output is a link to the workflow's runs
page. So this records the start time, dispatches, and polls for a run created at or after
that time on the same commit. Two dispatches on the same commit is a real case; the newest
one is taken, and **the id is printed** so a wrong pick is visible rather than silent.

Exit status
-----------

* ``0``   the run succeeded;
* ``1``   **the run concluded in failure**, or its artifact refused to be read;
* ``2``   an unknown task, or the dispatch never appeared before ``--timeout``;
* ``3``   **``gh`` could not be reached**, so the run's outcome is unknown.

``1`` and ``3`` are deliberately different, and that is the point of ``3``. A run that
concluded ``failure`` is a **result**: the measurement is on GitHub, the artifact is
printed, and a caller should read it. A ``gh`` call that fails three times is **not a
result**: nothing was learned about the run at all. Reporting both as ``1`` tells a caller
"the GUI suite failed" when what happened is "this machine could not ask GitHub", which is
the same conflation #190 removed from the log filter.

**Transient ``gh`` failures are retried before either of those is reported.** This machine
reaches GitHub through a local proxy that flakes -- a TLS handshake timeout mid-run is
routine, and it was reported as the tool failing while the run was still going and fine.
So each ``gh`` command is attempted ``GH_ATTEMPTS`` times with ``GH_BACKOFF`` seconds
between attempts, and a TLS timeout on the run *view* no longer ends the tool.

When it does give up, **the run id and the URL are printed whether or not the run could be
read**, because the reader has to be able to go and look. The URL is taken from ``gh run
list`` when that call answered, and otherwise built from the ``origin`` remote -- locally,
because asking GitHub for it is the one call that cannot be made.

The artifact contents go to stdout; every progress and diagnostic line goes to stderr, so
``python tools/gui_run.py m0 --artifact-file m0.json | jq .`` works.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The one workflow that runs a Java UI test.
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "windows-gui.yml"
WORKFLOW_NAME = "windows-gui.yml"

#: The workflow's own name for the artifact, from its ``upload-artifact`` step.
ARTIFACT_TEMPLATE = "windows-gui-{task}-jdk{java}"

#: The JDK versions the workflow offers, in its own order.
JAVA_VERSIONS = ("8", "11", "17", "21")

#: The dispatch default, used when the workflow does not say.
DEFAULT_TASK = "gui-suite"

#: How often the run list is asked, and how long a dispatch is waited for by default.
#: An interval rather than a fixed sleep: a fixed one is either too short -- and the run is
#: not listed yet -- or dead time, and there is no single value that is neither.
POLL_INTERVAL = 5.0
DEFAULT_TIMEOUT = 1800.0

#: How many times one ``gh`` command is attempted, and the wait between attempts.
#:
#: Three, because the failure this is for is the local proxy dropping a connection rather
#: than GitHub being down: measured on this machine, a TLS handshake timeout is a
#: one-off, and the same command answers on the next attempt. Two would leave no room for
#: two flakes in a row; more than three turns a genuinely unreachable GitHub into a long
#: wait for an answer that is not coming.
#:
#: The backoff is short and fixed. An exponential one would be tidier and is not worth it
#: here: three attempts of a call that answers in well under a second is a few seconds
#: either way, and the whole budget is visible in one constant.
GH_ATTEMPTS = 3
GH_BACKOFF = 2.0

#: The machine's current UTC offset, because a bare ``gh run list`` timestamp is local
#: time while the ``--json`` one is UTC. Taken as a fixed offset rather than through
#: ``zoneinfo``: ``ZoneInfo("localtime")`` is not portable, and a single dispatch does not
#: span a DST change. See ``parse_time``.
LOCAL_OFFSET = datetime.datetime.now().astimezone().tzinfo or datetime.timezone.utc


class GuiRunError(Exception):
    """Something the caller has to be told about rather than a traceback."""


class GhUnreachable(Exception):
    """``gh`` could not answer, after every attempt.

    Deliberately **not** a :class:`GuiRunError`. The handlers for that one answer ``1``,
    which means "the run concluded in failure" -- and this is the opposite of a
    conclusion. Every place that catches a ``GuiRunError`` has to say what it does about
    an unreachable GitHub instead of inheriting ``1`` by accident, so the two are separate
    types and the exit code is chosen at each site rather than by the class hierarchy.
    """


# ---------------------------------------------------------------------------
# The workflow file: which tasks exist, and what the run is called
# ---------------------------------------------------------------------------

def read_workflow(text: str) -> tuple:
    """``(tasks, default_task)`` for the ``workflow_dispatch`` task input.

    Read out of the file rather than kept in a list here. A copy would be correct until
    somebody renamed a task in the workflow, at which point this tool would dispatch a
    filter that matches nothing -- which is the failure #190 is about, moved rather than
    removed.

    The reader is deliberately narrow: it anchors on the ``workflow_dispatch`` trigger and
    then on the ``task:`` input inside it, so a ``task`` key anywhere else -- a step name,
    a job id -- cannot be mistaken for the input. It is not a general YAML parser, and it
    should not become one; if this file's shape ever grows past what this reads, the right
    answer is a real parser rather than a cleverer one of these.
    """
    tasks: list = []
    default = None

    lines = text.splitlines()
    dispatch_at = None
    dispatch_indent = None
    for index, line in enumerate(lines):
        if line.strip() == "workflow_dispatch:":
            dispatch_at = index
            dispatch_indent = len(line) - len(line.lstrip())
            break
    if dispatch_at is None:
        raise GuiRunError(
            f"{WORKFLOW_FILE.name} has no 'workflow_dispatch:' trigger, so this tool "
            "cannot tell which tasks exist"
        )

    # A key at or above the trigger's own indentation ends it, whatever it is, so the
    # sibling triggers of an `on:` block -- and anything after them -- are not searched.
    task_at = None
    for index in range(dispatch_at + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= dispatch_indent:
            break
        if line.strip() == "task:":
            task_at = index
            break
    if task_at is None:
        raise GuiRunError(
            f"the workflow_dispatch inputs in {WORKFLOW_FILE.name} have no 'task:' input"
        )

    input_at = len(lines[task_at]) - len(lines[task_at].lstrip())
    for index in range(task_at + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= input_at:
            break
        stripped = line.strip()
        if stripped.startswith("default:"):
            default = stripped.split(":", 1)[1].strip().strip("'\"")
        elif stripped == "options:":
            option_at = indent
            for option in lines[index + 1:]:
                if not option.strip():
                    continue
                if len(option) - len(option.lstrip()) <= option_at:
                    break
                if option.strip().startswith("- "):
                    tasks.append(option.strip()[2:].strip().strip("'\""))

    if not tasks:
        raise GuiRunError(
            f"the 'task:' input in {WORKFLOW_FILE.name} lists no options, so there is "
            "nothing to dispatch"
        )
    return tasks, (default or DEFAULT_TASK)


def read_tasks(path: Path = None) -> tuple:
    """The same, from the workflow file in the tree."""
    path = WORKFLOW_FILE if path is None else path
    return read_workflow(path.read_text(encoding="utf-8"))


def artifact_name(task: str, java: str) -> str:
    """The artifact the workflow uploads for one dispatch."""
    return ARTIFACT_TEMPLATE.format(task=task, java=java)


# ---------------------------------------------------------------------------
# Which run is the one that was just dispatched
# ---------------------------------------------------------------------------

def parse_time(stamp: str) -> datetime.datetime:
    """One of ``gh``'s ISO-8601 timestamps, as an aware UTC datetime.

    Both spellings matter and they are not interchangeable. ``gh run list --json
    createdAt`` answers **UTC with a ``Z``**; a bare timestamp from the ``gh run list``
    table, or one a person typed, is **local time** with no offset at all. The second is
    the dangerous one: read as UTC it moves every run by the machine's offset, and the
    pick then either finds nothing or finds the wrong run. ``fromisoformat`` handles the
    offset form itself; the ``Z`` is translated here for Python 3.9 and 3.10, which
    predate support for it.
    """
    text = str(stamp).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_OFFSET)
    return parsed.astimezone(datetime.timezone.utc)


def _field(run, *names):
    """A field from a run as ``gh run list --json`` gives it, or as a dict carries it.

    Both spellings are accepted because both happen: ``--json`` names the keys
    ``databaseId``, ``createdAt`` and ``headBranch``, while the actions API itself spells
    them ``id``, ``created_at`` and ``head_branch``.
    """
    for name in names:
        if isinstance(run, dict):
            if name in run and run[name] is not None:
                return run[name]
        elif hasattr(run, name):
            value = getattr(run, name)
            if value is not None:
                return value
    return None


def pick_run(runs: list, start: datetime.datetime, ref: str = None):
    """The newest run created at or after ``start``, or ``None``.

    ``start`` is when this tool began dispatching. Two dispatches on the same commit is a
    real case -- a maintainer trying a task, then trying it again -- and there is nothing
    in the run list that says which of them this invocation started. So the newest is
    taken and its id is printed: the ambiguity is not removed, it is made visible.

    `createdAt` is compared rather than an id ordering, because a database id is not
    documented to sort by creation and the timestamp is what the question is about.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)

    candidates = []
    for run in runs:
        created = _field(run, "createdAt", "created_at")
        if created is None:
            continue
        try:
            created = parse_time(created)
        except ValueError:
            continue
        if created < start:
            continue
        if ref is not None and _field(run, "headBranch", "head_branch") not in (None, ref):
            continue
        candidates.append((created, run))

    if not candidates:
        return None
    # Timestamp first; the id breaks a tie between two runs created in the same
    # millisecond, where "newest" would otherwise be whichever the API listed last.
    candidates.sort(key=lambda pair: (pair[0], str(_field(pair[1], "databaseId",
                                                           "database_id", "id"))))
    return candidates[-1][1]


def run_line(run) -> str:
    """One run as a line, for when a pick looks wrong.

    Naming the four fields that decide a pick rather than dumping the object: a reader who
    dispatched from a branch other than the one printed here has found the mistake, and
    that is the whole reason this exists.
    """
    return (f"  {_field(run, 'databaseId', 'database_id', 'id')}  "
            f"{_field(run, 'headBranch', 'head_branch')}  "
            f"{_field(run, 'createdAt', 'created_at')}  "
            f"{_field(run, 'status')}")


def poll_for_run(gh, ref: str, start: datetime.datetime,
                 timeout: float = DEFAULT_TIMEOUT, interval: float = POLL_INTERVAL,
                 monotonic=time.monotonic, sleep=time.sleep) -> dict:
    """Wait for the run that was just dispatched to appear in the run list.

    A bounded interval rather than one fixed ``sleep``: the run is listed within seconds
    when GitHub is quick and not at all for a while when it is not, and a fixed guess is
    wrong in one direction or the other every time.

    The timeout message names the things that actually produce this, because "no run
    appeared" after half an hour is otherwise indistinguishable from a dispatch that
    failed: a dispatch from a branch other than ``ref``, or a clock that disagrees with
    GitHub's.

    ``monotonic`` is the same injectable-clock seam as ``main``'s ``now``, and for the
    same reason.
    """
    deadline = monotonic() + timeout
    while True:
        run = pick_run(gh.list_runs(WORKFLOW_NAME), start, ref)
        if run is not None:
            return run
        if monotonic() >= deadline:
            raise TimeoutError(
                f"no run of {WORKFLOW_NAME} on {ref} appeared within {timeout:g}s of the "
                f"dispatch ({start.astimezone().isoformat()}). Either nothing was "
                "dispatched, or it went to another branch -- --ref says which -- or this "
                "machine's clock is behind GitHub's. `gh run list "
                "--workflow=windows-gui.yml --limit 5` shows what is there."
            )
        sleep(interval)


def await_run(gh, run_id, timeout: float = DEFAULT_TIMEOUT, interval: float = POLL_INTERVAL,
              monotonic=time.monotonic, sleep=time.sleep) -> str:
    """Wait for one run to finish, and answer with its conclusion.

    Bounded by the same ``--timeout``, and it does not raise on that: a run that is still
    going when the timeout arrives has a status rather than a failure, and it is printed.
    """
    deadline = monotonic() + timeout
    status = ""
    while True:
        status, conclusion = gh.run_status(run_id)
        if status == "completed":
            return conclusion or ""
        if monotonic() >= deadline:
            return f"still {status or 'unknown'} after {timeout:g}s"
        sleep(interval)


# ---------------------------------------------------------------------------
# Reading the artifact
# ---------------------------------------------------------------------------

def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:  # symlink loop, permission, ...
        return False


def artifact_files(root: Path) -> list:
    """Every regular file under an extracted artifact, relative, in path order."""
    root = Path(root)
    return sorted(path.relative_to(root) for path in root.rglob("*") if _is_file(path))


def find_artifact_file(root: Path, wanted: str) -> Path:
    """The one file in an extracted artifact that ``wanted`` names.

    Matched as a path relative to the artifact root, so ``--artifact-file gui-suite.log``
    is the ordinary case and ``--artifact-file sub/dir.log`` works when a task nests one.
    A **bare name is also matched at any depth**, because GitHub flattens the paths it
    uploads and the maintainer's mental model of the file is its name rather than where the
    action happened to put it.

    An exact match wins over a bare-name match, so ``a/x.log`` is unambiguous even when
    ``b/x.log`` also exists.
    """
    root = Path(root)
    wanted_path = Path(wanted)
    names = artifact_files(root)
    exact = root / wanted_path
    if _is_file(exact) and wanted_path.as_posix() in [name.as_posix() for name in names]:
        return exact

    matches = [name for name in names if name.name == wanted_path.name]
    if not matches:
        present = ", ".join(name.as_posix() for name in names) or "nothing"
        raise GuiRunError(f"no {wanted!r} in the artifact; it holds: {present}")
    if len(matches) > 1:
        listed = ", ".join(name.as_posix() for name in matches)
        raise GuiRunError(
            f"{wanted!r} matches more than one file in the artifact: {listed}. "
            "Name one by its path relative to the artifact."
        )
    return root / matches[0]


def print_artifact(root: Path, wanted: str = None) -> int:
    """Print the artifact's files, or the one ``wanted`` names.

    All of them by default: the workflow uploads whatever the task wrote, the filenames are
    the task's business, and a default that needed to know them would be wrong for every
    task added later.
    """
    if wanted is None:
        names = artifact_files(root)
        if not names:
            raise GuiRunError("the artifact was downloaded and holds no files")
    else:
        names = [find_artifact_file(root, wanted).relative_to(Path(root))]

    for name in names:
        print(f"===== {name} =====")
        print((Path(root) / name).read_text(encoding="utf-8", errors="replace"))
    return 0


# ---------------------------------------------------------------------------
# gh
# ---------------------------------------------------------------------------

def run_gh(args: list, timeout: float = None, attempts: int = GH_ATTEMPTS,
           backoff: float = GH_BACKOFF, sleep=time.sleep) -> str:
    """Run one ``gh`` command, retrying a transient failure, and return its stdout.

    A list rather than a shell string: the repository path contains spaces, and every
    argument here is data.

    **Every** command goes through here, so this is the one place the retry belongs. The
    failure being retried is not "the command was wrong" -- it is the local proxy dropping
    a connection, which is transient by nature and answered correctly on the next attempt.

    Two things are deliberately not distinguished:

    * a permanent ``gh`` error (``not logged in``, a 404) is retried like a transient one.
      Telling them apart means matching gh's stderr text, and guessing wrong in the
      permissive direction costs three attempts of a fast local failure -- a couple of
      seconds -- while guessing wrong in the strict direction means *not* retrying the
      flake this exists for. The message is carried through, so ``not logged in`` is still
      what the reader sees;
    * ``gh`` missing from ``PATH`` is also three attempts. They fail immediately, so the
      cost is nothing, and it keeps one code path.

    ``sleep`` is an injectable seam for the same reason the clocks in :func:`main` are: a
    test that really waited ``GH_BACKOFF`` would slow the suite down for no information.
    """
    args = list(args)
    describe = "gh " + " ".join(str(a) for a in args)
    last = "no output"

    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run(["gh"] + args, capture_output=True, text=True,
                                    timeout=timeout)
        except (OSError, subprocess.SubprocessError) as error:
            # gh not installed, or the call took longer than `timeout`. Both are the same
            # answer to this loop: this attempt did not produce a usable result.
            last = f"{type(error).__name__}: {error}"
        else:
            if result.returncode == 0:
                return result.stdout
            last = (result.stderr or result.stdout or "").strip() or "no output"

        if attempt < attempts:
            print(f"{describe} failed (attempt {attempt}/{attempts}): {last}",
                  file=sys.stderr)
            sleep(backoff)

    raise GhUnreachable(
        f"could not reach GitHub: {describe} failed on all {attempts} attempts; "
        f"last failure: {last}"
    )


def parse_remote(text: str) -> str:
    """``owner/name`` from a git remote URL, or ``""``.

    Both spellings are in use -- HTTPS with an optional ``.git``, and the scp-like
    ``git@github.com:owner/name`` -- so both are handled. Anything else, including a
    remote on another host, answers ``""`` rather than a wrong guess.
    """
    match = re.search(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$",
                      (text or "").strip())
    return match.group(1) if match else ""


def infer_repo() -> str:
    """``owner/name`` from the ``origin`` remote, or ``""``.

    Local, and that is the whole point: this is called on the path where GitHub could not
    be reached, so asking ``gh repo view`` for it would be the one call that cannot be
    made. ``git`` is already a dependency of this tool -- :func:`current_branch` runs it.
    """
    try:
        result = subprocess.run(["git", "remote", "get-url", "origin"],
                                capture_output=True, text=True)
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return parse_remote(result.stdout)


def run_url(repo: str, run_id=None) -> str:
    """The page a reader can open for a run, or for the workflow when there is no id.

    Built rather than read, because the case this exists for is the one where reading
    failed. ``""`` when the repository is not known -- a URL with a missing owner is worse
    than no URL, because it looks like an answer.
    """
    if not repo:
        return ""
    if run_id is None:
        return f"https://github.com/{repo}/actions/workflows/{WORKFLOW_NAME}"
    return f"https://github.com/{repo}/actions/runs/{run_id}"


def where_to_look(run_id=None, url: str = "", repo: str = "") -> str:
    """One line naming the run, printed when the tool gives up.

    ``url`` wins when it is there: it came from ``gh run list``, so it is what GitHub calls
    the run -- including on a GitHub Enterprise host, which the built one would get wrong.
    The run id is printed even when the URL is not, because ``gh run view <id>`` works from
    any checkout of this repository.
    """
    if run_id is None:
        page = run_url(repo)
        if page:
            return f"no run identified; the runs of {WORKFLOW_NAME} are at {page}"
        return (f"no run identified; `gh run list --workflow={WORKFLOW_NAME}` shows what "
                "is there")
    if url:
        return f"run {run_id}: {url}"
    page = run_url(repo, run_id)
    if page:
        return f"run {run_id}: {page}"
    return f"run {run_id}: `gh run view {run_id}`"


class Gh:
    """The gh calls this tool makes, behind one seam so the flow can be tested.

    Everything below is I/O against GitHub. The decisions -- which task, which run, which
    file -- are pure functions above, because those are the parts that are wrong silently.

    ``runner`` is the retrying :func:`run_gh` by default, so every command below inherits
    the retry. A test that injects a runner replaces the retry with it as well, which is
    why the retry has tests of its own at the :func:`run_gh` level rather than only through
    this class.
    """

    def __init__(self, repo: str = None, runner=run_gh):
        self.repo = repo
        self._run = runner

    def _repo(self) -> list:
        return ["--repo", self.repo] if self.repo else []

    def dispatch(self, task: str, java: str, ref: str, **inputs) -> None:
        fields = ["-f", f"task={task}", "-f", f"java={java}"]
        for key, value in inputs.items():
            if value is not None:
                fields += ["-f", f"{key}={value}"]
        self._run(["workflow", "run", WORKFLOW_NAME, "--ref", ref] + fields + self._repo())

    def list_runs(self, workflow: str, limit: int = 20) -> list:
        # `url` is asked for so the give-up path can name the run without a second call,
        # which is the call that would fail.
        raw = self._run([
            "run", "list", f"--workflow={workflow}", "--limit", str(limit),
            "--json", "databaseId,createdAt,status,headBranch,url",
        ] + self._repo())
        return json.loads(raw or "[]")

    def run_status(self, run_id) -> tuple:
        raw = self._run(["run", "view", str(run_id), "--json", "status,conclusion"]
                        + self._repo())
        data = json.loads(raw or "{}")
        return data.get("status") or "", data.get("conclusion") or ""

    def download_artifact(self, run_id, name: str, into: Path) -> None:
        self._run(["run", "download", str(run_id), "--name", name, "--dir", str(into)]
                  + self._repo())


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

def parse_args(argv: list, tasks: list) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gui_run.py",
        description="Dispatch one GUI task to windows-gui.yml and print what it measured.",
        epilog=(
            "valid tasks: " + ", ".join(tasks) + "\n\n"
            "exit status:\n"
            "  0  the run succeeded\n"
            "  1  the run concluded in failure (its artifact is still printed), or the\n"
            "     artifact could not be read\n"
            "  2  unknown task, or the dispatch never appeared before --timeout\n"
            "  3  gh could not be reached after " + str(GH_ATTEMPTS) + " attempts, so the\n"
            "     run's outcome is unknown -- this is NOT the same as 1\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", metavar="<task>",
                        help="the workflow_dispatch task to run")
    parser.add_argument("--java", default="17", choices=list(JAVA_VERSIONS),
                        help="Temurin JDK version (default: 17)")
    parser.add_argument("--artifact-file", metavar="NAME", default=None,
                        help="print only this file from the artifact (default: all of them)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS",
                        help=f"how long to wait for the run (default: {DEFAULT_TIMEOUT:g})")
    parser.add_argument("--ref", default=None,
                        help="the branch to dispatch (default: the current branch)")
    parser.add_argument("--repo", default=None, metavar="OWNER/NAME",
                        help="the GitHub repository (default: the one gh infers)")
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL, metavar="SECONDS",
                        help=f"how often to ask whether the run exists (default: {POLL_INTERVAL:g})")
    parser.add_argument("--minutes", default=None,
                        help="workflow input: duration for task=soak")
    args = parser.parse_args(argv)

    if args.task not in tasks:
        parser.error(
            f"unknown task {args.task!r}; the workflow offers: " + ", ".join(tasks)
        )
    return args


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def current_branch() -> str:
    """The branch to dispatch on, which is the one being worked on.

    ``--ref`` overrides it, and that is the useful half: once this workflow file is on the
    default branch, it can be dispatched from any branch, so a change can be measured
    before it is merged.
    """
    result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True)
    return result.stdout.strip() or "master"


def main(argv: list = None, gh=None, sleep=time.sleep, now=None,
         monotonic=time.monotonic, workflow: Path = None) -> int:
    """Dispatch, wait, print, and answer with a status.

    ``now`` and ``monotonic`` are the clock seams, and they are parameters for one reason.
    The tool identifies its run by comparing GitHub's ``createdAt`` against its own start
    time, so a test whose fixture is stamped by the test process' clock depends on the
    *difference between two clocks* pointing the right way. A run created a millisecond
    before ``start`` is correctly excluded -- and the test then polls for the full default
    timeout and hangs rather than failing, which is what this tool's own first version did
    in CI. Injecting the clocks makes the test say what the time is.
    """
    tasks, _default = read_tasks(workflow)
    args = parse_args(sys.argv[1:] if argv is None else argv, tasks)

    ref = args.ref or current_branch()
    repo = args.repo or infer_repo()
    client = gh if gh is not None else Gh(args.repo)
    start = (now or (lambda: datetime.datetime.now(datetime.timezone.utc)))()

    # Both are filled in as soon as they are known, and printed by every give-up path
    # below. A reader told "gh could not be reached" with no run id has to go and work out
    # which run was meant, which is the half of this that is not a tool's business.
    run_id = None
    url = ""

    print(f"dispatching task={args.task} java={args.java} on {ref}", file=sys.stderr)
    try:
        client.dispatch(args.task, args.java, ref, minutes=args.minutes)
    except GhUnreachable as error:
        # Whether the dispatch landed is unknown: the request may have been sent and its
        # answer lost. Say so rather than implying it did or did not.
        print(f"error: {error}", file=sys.stderr)
        print("the dispatch may or may not have been triggered -- an attempt that timed "
              "out may still have been delivered", file=sys.stderr)
        print(where_to_look(repo=repo), file=sys.stderr)
        return 3
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    try:
        run = poll_for_run(client, ref, start, timeout=args.timeout,
                           interval=args.interval, monotonic=monotonic, sleep=sleep)
        run_id = _field(run, "databaseId", "database_id", "id")
        url = _field(run, "url") or ""
        if run_id is None:
            raise GuiRunError(f"the run list answered with no id: {run!r}")
        # The id and the three fields that decided it. Two dispatches on one commit is a
        # real case, and this line is what turns a wrong pick into a visible one.
        print(f"run {run_line(run)}", file=sys.stderr)
        conclusion = await_run(client, run_id, timeout=args.timeout,
                               interval=args.interval, monotonic=monotonic, sleep=sleep)
    except TimeoutError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except GhUnreachable as error:
        # The run is going -- or has finished -- and this machine cannot ask. That is not
        # "the run failed", so it is not 1.
        print(f"error: {error}", file=sys.stderr)
        print(where_to_look(run_id, url, repo), file=sys.stderr)
        return 3
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    name = artifact_name(args.task, args.java)
    try:
        with tempfile.TemporaryDirectory(prefix="gui-run-") as directory:
            into = Path(directory) / name
            client.download_artifact(run_id, name, into)
            print_artifact(into, args.artifact_file)
    except GhUnreachable as error:
        # The run's conclusion is known here; its measurement is not. Naming the run is
        # what lets the reader fetch the artifact by hand.
        print(f"error: {error}", file=sys.stderr)
        print(where_to_look(run_id, url, repo), file=sys.stderr)
        return 3
    except (GuiRunError, ValueError, TypeError) as error:
        # ValueError is a gh answer that is not JSON -- an HTML error page, say -- and
        # TypeError is one that is JSON but not the shape expected. The run's conclusion is
        # still known, so the status code is decided below rather than here.
        print(f"could not read the artifact {name!r}: {error}", file=sys.stderr)
        return 1

    if conclusion != "success":
        print(f"run {run_id} finished {conclusion}", file=sys.stderr)
        return 1

    print(f"run {run_id} succeeded", file=sys.stderr)
    return 0


def cli() -> int:
    try:
        return main()
    except GhUnreachable as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(cli())
