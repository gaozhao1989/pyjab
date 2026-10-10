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
* ``1``   the run failed, or its artifact refused to be read;
* ``2``   an unknown task, or the dispatch never appeared before ``--timeout``.

The artifact contents go to stdout; every progress and diagnostic line goes to stderr, so
``python tools/gui_run.py m0 --artifact-file m0.json | jq .`` works.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
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

#: The machine's current UTC offset, because a bare ``gh run list`` timestamp is local
#: time while the ``--json`` one is UTC. Taken as a fixed offset rather than through
#: ``zoneinfo``: ``ZoneInfo("localtime")`` is not portable, and a single dispatch does not
#: span a DST change. See ``parse_time``.
LOCAL_OFFSET = datetime.datetime.now().astimezone().tzinfo or datetime.timezone.utc


class GuiRunError(Exception):
    """Something the caller has to be told about rather than a traceback."""


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

def run_gh(args: list, timeout: float = None) -> str:
    """Run one ``gh`` command and return its stdout.

    A list rather than a shell string: the repository path contains spaces, and every
    argument here is data.
    """
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True,
                            timeout=timeout)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip() or "no output"
        raise GuiRunError(f"gh {' '.join(str(a) for a in args)} failed: {message}")
    return result.stdout


class Gh:
    """The gh calls this tool makes, behind one seam so the flow can be tested.

    Everything below is I/O against GitHub. The decisions -- which task, which run, which
    file -- are pure functions above, because those are the parts that are wrong silently.
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
        raw = self._run([
            "run", "list", f"--workflow={workflow}", "--limit", str(limit),
            "--json", "databaseId,createdAt,status,headBranch",
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
        epilog="valid tasks: " + ", ".join(tasks),
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
    client = gh if gh is not None else Gh(args.repo)
    start = (now or (lambda: datetime.datetime.now(datetime.timezone.utc)))()

    print(f"dispatching task={args.task} java={args.java} on {ref}", file=sys.stderr)
    try:
        client.dispatch(args.task, args.java, ref, minutes=args.minutes)
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    try:
        run = poll_for_run(client, ref, start, timeout=args.timeout,
                           interval=args.interval, monotonic=monotonic, sleep=sleep)
        run_id = _field(run, "databaseId", "database_id", "id")
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
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    name = artifact_name(args.task, args.java)
    try:
        with tempfile.TemporaryDirectory(prefix="gui-run-") as directory:
            into = Path(directory) / name
            client.download_artifact(run_id, name, into)
            print_artifact(into, args.artifact_file)
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
    except GuiRunError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        raise SystemExit(cli())
