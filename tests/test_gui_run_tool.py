"""The decisions ``tools/gui_run.py`` makes, which are the parts that fail silently.

Dispatching the run needs GitHub, a Windows runner and a JVM, and none of that is here.
What is here is everything the tool decides *before* it touches any of them: which tasks
exist, which run in a list is the one just dispatched, and which file in an artifact is the
one that was asked for.

Those are worth testing because every one of them is a filter. Issue #190 is a filter that
matched nothing and looked like "nothing to report":

* the task list has to come from the workflow file, so a renamed task is refused here
  rather than dispatched into a step whose ``if:`` matches nothing;
* the run has to be picked by creation time, because ``gh workflow run`` returns no id and
  two dispatches on one commit is a case that really happens;
* the artifact file has to be found by name, because the alternative -- the previous
  tool's ``awk -F'\\t' '$2 ~ /task=.../'`` -- is the failure being removed.

A note on patching, since this project has been caught by it repeatedly (AGENTS.md 2.2):
``@singleton`` replaces a class with a wrapper *function*, so ``patch.object(Class, ...)``
silently does nothing and the test passes for a reason unrelated to its name. This tool has
no singletons -- the patchable seam is the injectable ``gh`` object -- so the rule does not
bite here. It is written down because the next person to add one will need it.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load():
    """gui_run by path: tools/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "gui_run", REPO_ROOT / "tools" / "gui_run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gui_run"] = module
    spec.loader.exec_module(module)
    return module


gui_run = load()


# ---------------------------------------------------------------------------
# Fakes, so the flow can be driven without GitHub
# ---------------------------------------------------------------------------

class FakeGh:
    """The ``gh`` seam, scripted.

    Records the calls it is given, so a test can assert on what would have been run as well
    as on what came back. ``download`` writes the files the dispatch was meant to produce.
    """

    def __init__(self, runs=None, statuses=(), files=None):
        #: What each successive ``list_runs`` answers. A list of lists, because the
        #: interesting case is the run *not being there yet*; the last answer repeats, so
        #: most tests pass one list and mean "this is what the run list holds".
        self._runs = [[a_run(1, just_dispatched())]] if runs is None else list(runs)
        if not self._runs:
            self._runs = [[]]
        self._statuses = list(statuses) or [("completed", "success")]
        self._files = files if files is not None else {"jvm-discovery.log": "the log\n"}
        self.calls = []
        self.status_polls = 0

    def dispatch(self, task, java, ref, **inputs):
        self.calls.append(("dispatch", task, java, ref,
                           tuple(sorted((k, str(v)) for k, v in inputs.items() if v))))

    def list_runs(self, workflow, limit=20):
        self.calls.append(("list_runs", workflow))
        if len(self._runs) > 1:
            return self._runs.pop(0)
        return self._runs[0]

    def run_status(self, run_id):
        self.calls.append(("run_status", run_id))
        self.status_polls += 1
        if len(self._statuses) > 1:
            return self._statuses.pop(0)
        return self._statuses[0]

    def download_artifact(self, run_id, name, into):
        self.calls.append(("download", run_id, name))
        into = Path(into)
        into.mkdir(parents=True, exist_ok=True)
        for relative, text in self._files.items():
            target = into / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")


def a_run(run_id, created, branch="master", status="completed"):
    return {"databaseId": run_id, "createdAt": created, "headBranch": branch,
            "status": status}


#: The flow tests pass ``--ref master`` rather than letting ``main`` read the checkout's
#: branch. The dispatch ref and the branch a run is on are the same thing, so a test that
#: used the real one would pass or fail depending on which branch CI checked out -- and the
#: first version of this file hung on exactly that, because the fake run is on ``master``
#: and the tool was looking for a run on the feature branch.
#:
#: The instant every flow test pretends the dispatch happened, handed to ``main`` as its
#: ``now``. Fixed rather than the real clock, because the first version of this file used
#: the real one and CI hung: a run created a millisecond before ``main`` recorded its start
#: is *correctly* excluded by the picker, so the test polled for the full 1800-second
#: default timeout instead of failing. Two processes' clocks agreeing is not a test
#: assumption worth making.
DISPATCHED_AT = datetime.datetime(2026, 10, 10, 10, 0, 0, tzinfo=datetime.timezone.utc)


def stamp(moment):
    """A datetime the way ``gh run list --json`` spells it."""
    return moment.isoformat().replace("+00:00", "Z")


def just_dispatched(offset=5):
    """A ``createdAt`` just after ``DISPATCHED_AT``, so the picker has to accept it."""
    return stamp(DISPATCHED_AT + datetime.timedelta(seconds=offset))


def frozen_clock():
    return DISPATCHED_AT


def no_sleep(_seconds):
    """The polls happen; the waiting does not."""


# ---------------------------------------------------------------------------
# The task list, read out of the real workflow file
# ---------------------------------------------------------------------------

def test_every_task_the_workflow_offers_is_read():
    """Against the real file, because a copy of this list is the bug (#190).

    The tool has to refuse a task the workflow does not have. It can only do that if it
    knows what the workflow has, and a hard-coded list here would be right until somebody
    renamed a task -- at which point this tool dispatches a filter matching nothing, which
    is the failure it exists to remove, moved rather than fixed.
    """
    tasks, default = gui_run.read_tasks()

    assert tasks == [
        "gui-suite", "m0", "xpath", "table-selection", "dpi", "dpi-scaled", "test-app",
        "soak", "jvm-discovery", "visible-children-count", "screenshot", "detach",
        "environment",
    ]
    assert default == "gui-suite"


def test_a_renamed_task_is_refused_and_the_valid_names_are_printed(capsys):
    """A task that does not exist must fail loudly rather than dispatch nothing."""
    with pytest.raises(SystemExit) as exit_info:
        gui_run.parse_args(["gui-suites"], ["gui-suite", "m0"])

    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "gui-suites" in err
    assert "gui-suite" in err, "the valid names have to be printed, not just the bad one"


def test_the_reader_takes_the_options_from_the_task_input_not_a_step_name():
    """A ``task`` key anywhere else in the file must not be mistaken for the input.

    This is the #190 failure as a shape: the dispatch filter and the step that runs the
    task drifting apart. The reader has to anchor on the trigger and then on the input, or
    it will happily read a step's name as the list of tasks.
    """
    text = (
        "name: Something\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      task:\n"
        "        default: gui-suite\n"
        "        options:\n"
        "          - first\n"
        "          - second\n"
        "      java:\n"
        "        default: \"17\"\n"
        "        options:\n"
        "          - \"8\"\n"
        "          - \"17\"\n"
        "jobs:\n"
        "  windows-gui:\n"
        "    steps:\n"
        "      - name: \"task=first\"\n"
        "        run: echo hi\n"
    )

    tasks, default = gui_run.read_workflow(text)

    assert tasks == ["first", "second"]
    assert default == "gui-suite"


def test_a_workflow_without_the_trigger_is_an_error_not_an_empty_list():
    """An empty task list would refuse every task, which reads as the tool being broken."""
    with pytest.raises(gui_run.GuiRunError) as error:
        gui_run.read_workflow("name: Nothing\njobs: {}\n")

    assert "workflow_dispatch" in str(error.value)


def test_a_task_with_no_options_is_an_error():
    with pytest.raises(gui_run.GuiRunError):
        gui_run.read_workflow(
            "on:\n"
            "  workflow_dispatch:\n"
            "    inputs:\n"
            "      task:\n"
            "        description: What to run\n"
        )


def test_an_unknown_task_has_no_artifact_name_to_guess():
    """The artifact name follows the task, so a wrong task is a wrong artifact too."""
    assert gui_run.artifact_name("m0", "8") == "windows-gui-m0-jdk8"
    assert gui_run.artifact_name("visible-children-count", "17") == \
        "windows-gui-visible-children-count-jdk17"


def test_the_defaults_match_the_workflow():
    """``java: 17`` is the workflow's own default, and the parser has to agree."""
    args = gui_run.parse_args(["m0"], ["m0"])
    assert args.java == "17"
    assert args.artifact_file is None


def test_an_unknown_jdk_is_refused():
    with pytest.raises(SystemExit) as exit_info:
        gui_run.parse_args(["m0", "--java", "7"], ["m0"])
    assert exit_info.value.code == 2


# ---------------------------------------------------------------------------
# Which run is the one that was just dispatched
# ---------------------------------------------------------------------------

def test_the_run_created_at_or_after_the_dispatch_is_the_one():
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    runs = [a_run(9, "2026-10-10T09:59:59Z"), a_run(10, "2026-10-10T10:00:00Z")]

    assert gui_run.pick_run(runs, start)["databaseId"] == 10


def test_a_run_from_before_the_dispatch_is_not_mistaken_for_it():
    """The run already on the branch is exactly the wrong answer."""
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    runs = [a_run(8, "2026-10-09T23:00:00Z")]

    assert gui_run.pick_run(runs, start) is None


def test_two_dispatches_on_one_commit_take_the_newest():
    """The real case the tool cannot resolve, so it has to at least be deterministic.

    There is nothing in the run list that says which of two same-commit dispatches this
    invocation started, so the newest is taken -- and ``main`` prints the id it used, which
    is what makes a wrong pick visible instead of silent.
    """
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    runs = [
        a_run(11, "2026-10-10T10:00:03Z"),
        a_run(12, "2026-10-10T10:00:05Z"),
        a_run(13, "2026-10-10T10:00:04Z"),
    ]

    assert gui_run.pick_run(runs, start)["databaseId"] == 12


def test_the_newest_is_taken_even_when_the_list_is_not_sorted():
    """``gh run list`` is newest-first today; depending on that would be a second bug."""
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    runs = [a_run(1, "2026-10-10T10:00:09Z"), a_run(2, "2026-10-10T10:00:01Z")]

    assert gui_run.pick_run(runs, start)["databaseId"] == 1


def test_two_runs_in_the_same_millisecond_are_still_ordered():
    """Not a case that happens, a case that must not be *nondeterministic*.

    ``createdAt`` has millisecond resolution and the tie-break is the id, so two runs
    stamped identically answer the same way every time rather than depending on the order
    the API happened to list them in.
    """
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    same = "2026-10-10T10:00:05Z"
    runs = [a_run(80, same), a_run(81, same)]

    assert gui_run.pick_run(runs, start)["databaseId"] == 81
    assert gui_run.pick_run(list(reversed(runs)), start)["databaseId"] == 81


def test_a_run_on_another_branch_is_not_ours():
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    runs = [a_run(20, "2026-10-10T10:00:05Z", branch="someone-elses-probe")]

    assert gui_run.pick_run(runs, start, ref="master") is None


def test_a_naive_start_time_is_read_as_utc_rather_than_raising():
    """``datetime.now()`` without a timezone must not make every run look in the past."""
    start = datetime.datetime(2026, 10, 10, 10, 0, 0)
    runs = [a_run(21, "2026-10-10T10:00:01Z")]

    assert gui_run.pick_run(runs, start)["databaseId"] == 21


def test_the_offset_form_of_timestamp_is_understood_as_well_as_z():
    """``gh`` has answered both spellings; only one of them is the documented one."""
    assert gui_run.parse_time("2026-10-10T10:00:00Z") == \
        gui_run.parse_time("2026-10-10T10:00:00+00:00")


def test_an_older_run_in_the_list_is_not_taken_while_polling():
    """The list holds the branch's previous runs; none of them is the one just dispatched."""
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    old = a_run(70, "2026-10-10T09:00:00Z")
    gh = FakeGh(runs=[[old], [old], [old, a_run(71, "2026-10-10T10:00:01Z")]])

    run = gui_run.poll_for_run(gh, "master", start, timeout=60, interval=1, sleep=no_sleep)

    assert run["databaseId"] == 71


def test_a_bare_timestamp_is_read_as_local_time_not_utc():
    """The two spellings ``gh`` produces are not interchangeable.

    ``--json createdAt`` is UTC with a ``Z``; the ``gh run list`` *table* prints local time
    with no offset at all. Reading the second as UTC moves every run by the machine's
    offset -- three hours here in summer -- and the pick then silently finds nothing, or
    the wrong run.
    """
    offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta(0)
    as_utc = gui_run.parse_time("2026-10-10T10:00:00Z")
    as_local = gui_run.parse_time("2026-10-10T10:00:00")

    # 10:00 local is 10:00 minus the offset in UTC, so the UTC spelling is the later one.
    assert as_utc - as_local == offset


def test_the_timeout_message_names_what_to_check_next(capsys):
    """A half-hour wait that says only "no run" is indistinguishable from a failure.

    The message is worth a test because it is the whole diagnosis: the branch is the
    likeliest mistake, and ``gh run list`` is the thing to compare against.
    """
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    gh = FakeGh(runs=[[]])

    with pytest.raises(TimeoutError) as error:
        gui_run.poll_for_run(gh, "my-branch", start, timeout=0, interval=1,
                             monotonic=lambda: 0.0, sleep=no_sleep)

    message = str(error.value)
    assert "my-branch" in message
    assert "--ref" in message
    assert "gh run list" in message


def test_polling_repeats_until_the_run_appears():
    """An interval, not a fixed sleep: the answer is asked for rather than guessed at."""
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    gh = FakeGh(runs=[[], [], [a_run(30, "2026-10-10T10:00:02Z")]])

    run = gui_run.poll_for_run(gh, "master", start, timeout=60, interval=1, sleep=no_sleep)

    assert run["databaseId"] == 30
    assert [call[0] for call in gh.calls] == ["list_runs"] * 3


def test_a_dispatch_that_never_appears_times_out():
    """Rather than polling for ever, or reading the run already on the branch."""
    start = gui_run.parse_time("2026-10-10T10:00:00Z")
    gh = FakeGh(runs=[[]])

    with pytest.raises(TimeoutError) as error:
        gui_run.poll_for_run(gh, "master", start, timeout=0, interval=1, sleep=no_sleep)

    assert "appeared" in str(error.value)


def test_waiting_returns_the_conclusion_once_the_run_completes():
    gh = FakeGh(statuses=[("in_progress", ""), ("completed", "success")])

    assert gui_run.await_run(gh, 40, timeout=60, interval=1, sleep=no_sleep) == "success"
    assert gh.status_polls == 2


def test_a_run_still_going_at_the_timeout_says_so_rather_than_claiming_success():
    gh = FakeGh(statuses=[("queued", "")])

    conclusion = gui_run.await_run(gh, 41, timeout=0, interval=1, sleep=no_sleep)

    assert conclusion != "success"
    assert "queued" in conclusion


# ---------------------------------------------------------------------------
# The artifact
# ---------------------------------------------------------------------------

def posix_names(root):
    """The artifact's files, forward-slashed.

    ``str(Path("a/b.txt"))`` is ``a/b.txt`` here and ``a\\b.txt`` on Windows, so an
    assertion written with the first spelling fails there. It did, on this file's second CI
    run, and the fix is to compare one spelling everywhere rather than to skip the test.
    """
    return [name.as_posix() for name in gui_run.artifact_files(root)]


def an_artifact(tmp_path, **files):
    for name, text in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def test_every_file_in_the_artifact_is_listed(tmp_path):
    root = an_artifact(tmp_path, **{"a.log": "1", "nested/b.txt": "2"})

    assert posix_names(root) == ["a.log", "nested/b.txt"]


def test_the_named_file_is_the_one_printed(tmp_path):
    """``m0`` writes ``m0.json`` where every other task writes ``<task>.log``."""
    root = an_artifact(tmp_path, **{"m0.json": "{}", "setup.log": "noise"})

    chosen = gui_run.find_artifact_file(root, "m0.json")

    assert chosen == root / "m0.json"


def test_a_bare_name_is_found_wherever_the_action_put_it(tmp_path):
    """``upload-artifact`` flattens paths; the maintainer knows the name, not the depth."""
    root = an_artifact(tmp_path, **{"logs/table-selection.log": "x"})

    assert gui_run.find_artifact_file(root, "table-selection.log") == \
        root / "logs" / "table-selection.log"


def test_a_name_that_is_not_there_says_what_is(tmp_path):
    """The failure this replaces: a filter that matched nothing and printed nothing."""
    root = an_artifact(tmp_path, **{"dpi.log": "x"})

    with pytest.raises(gui_run.GuiRunError) as error:
        gui_run.find_artifact_file(root, "m0.json")

    assert "m0.json" in str(error.value)
    assert "dpi.log" in str(error.value), "the names that are there are the useful half"


def test_two_files_with_one_name_are_refused_rather_than_guessed(tmp_path):
    root = an_artifact(tmp_path, **{"a/x.log": "one", "b/x.log": "two"})

    with pytest.raises(gui_run.GuiRunError) as error:
        gui_run.find_artifact_file(root, "x.log")

    assert "more than one" in str(error.value)


def test_a_path_disambiguates_two_files_with_one_name(tmp_path):
    root = an_artifact(tmp_path, **{"a/x.log": "one", "b/x.log": "two"})

    assert gui_run.find_artifact_file(root, "b/x.log") == root / "b" / "x.log"


def test_all_files_are_printed_when_none_is_named(tmp_path, capsys):
    """The default has to work for a task whose filename this tool does not know."""
    root = an_artifact(tmp_path, **{"m0.json": "{}", "extra.txt": "hello"})

    gui_run.print_artifact(root)

    out = capsys.readouterr().out
    assert "===== extra.txt =====" in out
    assert "===== m0.json =====" in out
    assert "hello" in out


def test_an_empty_artifact_is_an_error_not_a_silent_success(tmp_path):
    with pytest.raises(gui_run.GuiRunError):
        gui_run.print_artifact(tmp_path)


# ---------------------------------------------------------------------------
# The whole flow, with gh scripted
# ---------------------------------------------------------------------------

def test_a_successful_run_prints_the_artifact_and_returns_zero(capsys, tmp_path):
    gh = FakeGh(runs=[[a_run(50, just_dispatched())]])

    code = gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    assert code == 0
    out = capsys.readouterr().out
    assert "the log" in out
    assert ("dispatch", "jvm-discovery", "17", "master", ()) in gh.calls
    assert ("download", 50, "windows-gui-jvm-discovery-jdk17") in gh.calls


def test_the_run_id_is_printed_so_a_wrong_pick_is_visible(capsys):
    """The whole point of taking the newest rather than the first."""
    gh = FakeGh(runs=[[a_run(51, just_dispatched())]])

    gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    err = capsys.readouterr().err
    assert "51" in err


def test_the_run_line_names_the_fields_that_decided_the_pick(capsys):
    """The print exists so a wrong pick is visible; a bare number would not be enough."""
    gh = FakeGh(runs=[[a_run(57, just_dispatched(), branch="master")]])

    gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    err = capsys.readouterr().err
    assert "57" in err
    assert "master" in err
    assert just_dispatched() in err


def test_a_failed_run_returns_non_zero_after_printing_the_measurement(capsys):
    """A failed GUI run is exactly when the measurement is worth reading."""
    gh = FakeGh(runs=[[a_run(52, just_dispatched())]],
                statuses=[("completed", "failure")])

    code = gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    captured = capsys.readouterr()
    assert code == 1
    assert "the log" in captured.out, "the artifact has to be printed even when the run failed"
    assert "failure" in captured.err


def test_a_run_with_no_id_is_an_error_rather_than_a_query_for_none(capsys):
    """``gh`` is asked for ``databaseId``; a run without one cannot be watched."""
    run = a_run(None, just_dispatched())
    gh = FakeGh(runs=[[run]])

    code = gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    assert code == 1
    assert "no id" in capsys.readouterr().err


def test_an_answer_that_is_not_json_exits_non_zero_rather_than_tracing_back(capsys):
    gh = FakeGh(runs=[[a_run(56, just_dispatched())]])
    gh.download_artifact = MagicMock(side_effect=ValueError("Expecting value: line 1"))

    code = gui_run.main(["jvm-discovery", "--ref", "master"], gh=gh, sleep=no_sleep,
                 now=frozen_clock)

    assert code == 1
    assert "could not read the artifact" in capsys.readouterr().err


def test_a_dispatch_that_never_appears_exits_two(capsys):
    """2 is "could not tell", which is a different answer from "the run failed"."""
    # A run that exists and is not this invocation's: the dispatch that failed to appear
    # comes back as "there is nothing new", not as "there is an older run here".
    gh = FakeGh(runs=[[a_run(60, stamp(DISPATCHED_AT - datetime.timedelta(hours=1)))]])

    # The timeout is real here, which is why it is zero: with the default the "run never
    # appeared" path would take thirty minutes to demonstrate, and a test that hangs
    # instead of failing is how this file's first version reached CI.


    code = gui_run.main(["jvm-discovery", "--ref", "master", "--timeout", "0",
                          "--interval", "1"], gh=gh, sleep=no_sleep, now=frozen_clock)

    assert code == 2
    assert "error" in capsys.readouterr().err


def test_only_the_named_file_is_printed(capsys):
    gh = FakeGh(runs=[[a_run(53, just_dispatched())]],
                files={"m0.json": "{}", "m0.log": "noise"})

    gui_run.main(["m0", "--ref", "master", "--artifact-file", "m0.json"], gh=gh,
                 sleep=no_sleep, now=frozen_clock)

    out = capsys.readouterr().out
    assert "{}" in out
    assert "noise" not in out


def test_an_artifact_that_cannot_be_read_exits_non_zero(capsys):
    gh = FakeGh(runs=[[a_run(54, just_dispatched())]], files={"other.log": "x"})

    code = gui_run.main(["m0", "--ref", "master", "--artifact-file", "m0.json"], gh=gh,
                 sleep=no_sleep, now=frozen_clock)

    assert code == 1
    assert "m0.json" in capsys.readouterr().err


def test_minutes_is_passed_through_for_soak():
    gh = FakeGh(runs=[[a_run(55, just_dispatched())]])

    gui_run.main(["soak", "--ref", "master", "--minutes", "120", "--java", "8"], gh=gh,
                 sleep=no_sleep, now=frozen_clock)

    dispatch = [call for call in gh.calls if call[0] == "dispatch"][0]
    assert dispatch[1:4] == ("soak", "8", "master")
    assert ("minutes", "120") in dispatch[4]


# ---------------------------------------------------------------------------
# The command that actually reaches gh
# ---------------------------------------------------------------------------

def test_the_dispatch_carries_the_task_and_the_ref_to_the_workflow():
    """``task=... -f`` is what the workflow's ``if:`` matches on."""
    gh = gui_run.Gh("gaozhao1989/pyjab", runner=MagicMock(return_value=""))

    gh.dispatch("m0", "8", "my-probe")

    argv = gh._run.call_args[0][0]
    assert argv[:3] == ["workflow", "run", "windows-gui.yml"]
    assert "--ref" in argv and "my-probe" in argv
    assert "task=m0" in argv
    assert "java=8" in argv


def test_a_gh_failure_is_reported_rather_than_raising_from_subprocess():
    """One message from the tool, not a traceback from deep inside it."""
    with patch.object(gui_run.subprocess, "run") as run:
        run.return_value = MagicMock(returncode=1, stderr="gh: not logged in\n", stdout="")

        with pytest.raises(gui_run.GuiRunError) as error:
            gui_run.run_gh(["run", "list"])

    assert "not logged in" in str(error.value)


def test_the_run_list_asks_for_the_fields_the_picker_reads():
    """A field the picker reads but ``--json`` does not ask for is always absent."""
    gh = gui_run.Gh("owner/name", runner=MagicMock(
        return_value=json.dumps([a_run(1, "2026-10-10T10:00:00Z")])))

    gh.list_runs(gui_run.WORKFLOW_NAME)

    argv = gh._run.call_args[0][0]
    requested = argv[argv.index("--json") + 1]
    for field in ("databaseId", "createdAt", "headBranch"):
        assert field in requested, field
