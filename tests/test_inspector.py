"""``pyjab-inspect`` -- the parts that can be tested off Windows.

The JAB half of the CLI needs a real Java window, and the GUI suite only runs when a
human runs it. What is portable is everything the user actually reads: the tree
rendering, the locator suggestions, the step-by-step failure report, the argument
handling, and two pieces of behaviour that would be genuinely harmful if wrong.

Those two get most of the attention here:

* ``walk`` walks a real tree, and every child it touches is a JAB reference that has
  to be released exactly once -- ``tests/_fakejab.py`` counts references and raises on
  both mistakes, so the walk is checked against it rather than against a mock that
  would agree with anything;
* ``attached`` must not call ``JABDriver.__exit__`` when it attached to a window the
  user already had running, because ``__exit__`` terminates that process by pid. A
  locator tool that kills the application it was asked to look at would be memorable
  for the wrong reason.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import sys
from pathlib import Path

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import

from pyjab import inspector
from tests._fakejab import bind, node, panel

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Rendering and locator suggestions
# ---------------------------------------------------------------------------

def test_render_tree_indents_by_depth():
    entries = [
        (0, {"role": "frame", "name": "app", "index_in_parent": 0,
             "children_count": 1, "object_depth": 0, "states": "", "bounds": {}}),
        (1, {"role": "push button", "name": "OK", "index_in_parent": 0,
             "children_count": 0, "object_depth": 1, "states": "", "bounds": {}}),
    ]

    lines = inspector.render_tree(entries).splitlines()

    assert lines[0].startswith("frame")
    assert lines[1].startswith("  push button")
    assert "name='OK'" in lines[1]
    assert "children=0" in lines[1]


def test_render_tree_names_an_unnamed_element():
    """`name=''` reads like a bug; `(unnamed)` reads like the truth."""
    entries = [(0, {"role": "panel", "name": "", "index_in_parent": 0,
                    "children_count": 0, "object_depth": 0, "states": "",
                    "bounds": {}})]

    assert "(unnamed)" in inspector.render_tree(entries)


def test_bounds_are_only_shown_when_asked():
    entries = [(0, {"role": "label", "name": "x", "index_in_parent": 0,
                    "children_count": 0, "object_depth": 0, "states": "",
                    "bounds": {"x": 1, "y": 2, "width": 3, "height": 4}})]

    assert "bounds" not in inspector.render_tree(entries)
    assert "bounds=(1,2,3x4)" in inspector.render_tree(entries, show_bounds=True)


def test_a_locator_prefers_the_name_over_the_index():
    """An index is a position, and positions move. The name goes first."""
    item = {"role": "push button", "name": "Save", "description": "",
            "index_in_parent": 3, "children_count": 0, "object_depth": 2,
            "states": "", "bounds": {}}

    locators = inspector.suggest_locators(item, siblings=4)

    assert locators[0] == "//push button[@name='Save']"
    assert all("indexinparent" in later for later in locators[1:])


def test_an_indexed_locator_is_not_offered_when_the_name_is_unique():
    item = {"role": "push button", "name": "Save", "description": "",
            "index_in_parent": 0, "children_count": 0, "object_depth": 2,
            "states": "", "bounds": {}}

    assert inspector.suggest_locators(item, siblings=1) == ["//push button[@name='Save']"]


def test_a_name_with_an_apostrophe_is_quoted_the_other_way():
    """`//x[@name='it's']` is not a locator, it is a parse error."""
    item = {"role": "label", "name": "it's", "description": "",
            "index_in_parent": 0, "children_count": 0, "object_depth": 0,
            "states": "", "bounds": {}}

    assert inspector.suggest_locators(item)[0] == '//label[@name="it\'s"]'


def test_a_name_with_both_quotes_says_so_rather_than_emitting_rubbish():
    item = {"role": "label", "name": "it's \"quoted\"", "description": "",
            "index_in_parent": 0, "children_count": 0, "object_depth": 0,
            "states": "", "bounds": {}}

    with pytest.raises(ValueError):
        inspector.suggest_locators(item)


def test_an_element_with_no_name_still_gets_a_locator():
    item = {"role": "panel", "name": "", "description": "",
            "index_in_parent": 2, "children_count": 0, "object_depth": 1,
            "states": "", "bounds": {}}

    locators = inspector.suggest_locators(item)

    assert locators, "something has to be offered, or the tool is a dead end"
    assert "//panel" in locators[0]


# ---------------------------------------------------------------------------
# Walking a tree, and the references that costs
# ---------------------------------------------------------------------------

def test_walk_yields_plain_records_not_elements():
    """The reason it can release as it goes.

    If it yielded elements the caller could hold a reference after the walk released
    it, which is use-after-free.
    """
    element, _bridge = bind(node("frame", node("push button", name="OK"), name="app"))

    entries = list(inspector.walk(element, max_depth=None, limit=None))

    assert all(isinstance(item, dict) for _depth, item in entries)
    assert [item["name"] for _d, item in entries] == ["OK"]


def test_walk_releases_every_reference_it_takes():
    """The property that matters, checked by the bridge that counts them."""
    root = node("frame", panel(node("label", name="a"), node("label", name="b")),
                name="app")
    element, bridge = bind(root)
    before = dict(bridge.refs)

    list(inspector.walk(element, max_depth=None, limit=None))

    grew = {h: bridge.refs[h] - before.get(h, 0)
            for h in bridge.refs if bridge.refs[h] > before.get(h, 0)}
    assert not grew, f"walking the tree left {grew} outstanding"


def test_walk_stops_at_max_depth():
    element, _bridge = bind(node("frame", panel(node("label", name="deep")), name="mid"))

    entries = list(inspector.walk(element, max_depth=0, limit=None))

    assert [item["role"] for _d, item in entries] == ["panel"]


def test_walk_stops_at_the_limit():
    root = node("frame", *[node("label", name=f"l{i}") for i in range(10)], name="app")
    element, _bridge = bind(root)

    entries = list(inspector.walk(element, max_depth=None, limit=3))

    assert len(entries) == 3


def test_walk_records_the_depth_of_each_element():
    element, _bridge = bind(node("frame", panel(node("label", name="deep")), name="mid"))

    depths = [d for d, _item in inspector.walk(element, max_depth=None, limit=None)]

    assert depths == [0, 1]


# ---------------------------------------------------------------------------
# The step-by-step failure report
# ---------------------------------------------------------------------------

class FakeDriver:
    """Enough of a driver for step_report: it answers per locator.

    It runs the real predicate parser over each locator first, so a locator that
    does not parse raises ``XpathParserException`` exactly as the real driver does.
    A fake that answered "no such locator" for `//panel[last()]` would let a test
    claim the parse error reaches the user while the code actually swallowed it --
    which is what the first version of this fake did.
    """

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def find_elements_by_xpath(self, value, visible=False):
        from pyjab.common.exceptions import JABException, XpathParserException
        from pyjab.common.xpathparser import XpathParser

        self.asked.append(value)
        parser = XpathParser.__wrapped__()
        try:
            for node in parser.split_union(value):
                for piece in parser.split_nodes(node):
                    parser.get_node_information(piece)
        except XpathParserException:
            raise
        if value not in self.answers:
            raise JABException(f"no JABElement found by xpath '{value}'")
        return [object()] * self.answers[value]


def test_step_report_finds_which_step_stopped():
    """The whole point: 'no element found' does not say which step is wrong."""
    driver = FakeDriver({"//panel": 3, "//panel/label": 0})

    report = inspector.step_report(driver, "//panel/label")

    assert [item["count"] for item in report] == [3, 0]
    assert report[0]["step"] == "//panel"
    assert report[1]["step"] == "//panel/label"


def test_step_report_asks_each_prefix_once_in_order():
    driver = FakeDriver({"//panel": 1, "//panel/label": 1, "//panel/label/text": 1})

    inspector.step_report(driver, "//panel/label/text")

    assert driver.asked == ["//panel", "//panel/label", "//panel/label/text"]


def test_step_report_keeps_a_relative_locator_relative():
    """`.//x` searches from the element it was called on, and so must each prefix."""
    driver = FakeDriver({".//panel": 1, ".//panel/label": 2})

    report = inspector.step_report(driver, ".//panel/label")

    assert [item["step"] for item in report] == [".//panel", ".//panel/label"]


def test_step_report_does_not_treat_a_slash_in_a_value_as_a_step():
    """Rebuilt from the parsed nodes, so a quoted `/` cannot split the path."""
    driver = FakeDriver({"//panel[@name='a/b']": 1})

    report = inspector.step_report(driver, "//panel[@name='a/b']")

    assert len(report) == 1
    assert report[0]["count"] == 1


def test_step_report_reports_a_parse_error_rather_than_raising():
    driver = FakeDriver({})

    report = inspector.step_report(driver, "//panel[last()]")

    assert report[0]["error"], "the parse error has to reach the user"
    assert driver.asked == [], "and nothing should have been asked of JAB"


# ---------------------------------------------------------------------------
# Not killing the application we were asked to inspect
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_jabdriver(monkeypatch):
    """Install a stand-in ``pyjab.jabdriver`` for the duration of one test.

    The real module raises ImportError off Windows, so ``monkeypatch.setattr`` on one
    of its attributes needs it to be importable -- which it is only if an earlier
    test happened to leave it in ``sys.modules``. Three tests here passed in a full
    run and failed on their own because of that, which is a worse failure than
    failing outright: it hides until someone runs one file.
    """
    import types

    def install(driver_class):
        module = types.ModuleType("pyjab.jabdriver")
        module.JABDriver = driver_class
        monkeypatch.setitem(sys.modules, "pyjab.jabdriver", module)
        return driver_class
    return install


def test_attaching_does_not_terminate_the_application(stub_jabdriver):
    """`JABDriver.__exit__` kills the bound process by pid.

    Calling it after attaching would kill the user's own application -- the one they
    asked this tool to look at.
    """
    exits = []

    class FakeDriver:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __exit__(self, *args):
            exits.append(args)

    stub_jabdriver(FakeDriver)

    with inspector.attached("My App", 30, None) as driver:
        assert driver.kwargs["title"] == "My App"

    assert exits == [], "attaching must not tear the application down"


def test_launching_does_close_what_we_started(stub_jabdriver):
    exits = []

    class FakeDriver:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __exit__(self, *args):
            exits.append(args)

    stub_jabdriver(FakeDriver)

    with inspector.attached("My App", 30, "/tmp/app.jar") as driver:
        assert driver.kwargs["file_path"] == "/tmp/app.jar"

    assert len(exits) == 1, "the application we started is ours to stop"


def test_the_application_is_closed_even_when_the_body_raises(stub_jabdriver):
    exits = []

    class FakeDriver:
        def __init__(self, **kwargs):
            pass

        def __exit__(self, *args):
            exits.append(args)

    stub_jabdriver(FakeDriver)

    with pytest.raises(RuntimeError):
        with inspector.attached("My App", 30, "/tmp/app.jar"):
            raise RuntimeError("the body blew up")

    assert len(exits) == 1


# ---------------------------------------------------------------------------
# The command line itself
# ---------------------------------------------------------------------------

def test_every_subcommand_parses():
    for argv in [["windows"], ["tree", "T"], ["find", "T", "//x"],
                 ["locator", "T", "--name", "Save"]]:
        assert inspector.build_parser().parse_args(argv)


def test_a_subcommand_is_required():
    with pytest.raises(SystemExit):
        inspector.build_parser().parse_args([])


def test_tree_and_find_require_a_title():
    with pytest.raises(SystemExit):
        inspector.build_parser().parse_args(["tree"])
    with pytest.raises(SystemExit):
        inspector.build_parser().parse_args(["find", "//x"])


def test_it_says_it_needs_windows_instead_of_raising(monkeypatch, capsys):
    """A traceback where a sentence belongs is the wrong first impression."""
    def explode(_args):
        raise ImportError("no pythoncom on this platform")

    monkeypatch.setattr(inspector, "cmd_windows", explode)
    parser = inspector.build_parser()
    monkeypatch.setattr(inspector, "build_parser", lambda: parser)

    code = inspector.main(["windows"])

    assert code == 2
    assert "needs Windows" in capsys.readouterr().err


def test_the_entry_point_is_registered_and_points_somewhere_real():
    """A console script in pyproject that names a missing function fails at install.

    Read rather than imported: `tomllib` is only in the standard library from 3.11.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    assert 'pyjab-inspect = "pyjab.inspector:main"' in text
    assert callable(inspector.main)


def test_the_package_is_importable_without_windows():
    """It has to be, or the console script cannot even print the sentence above.

    pyjab.jabdriver raises ImportError at module scope off Windows, so this module
    must not import it there. Checked with the AST rather than by looking for the
    word: the module docstring names it, and so does the explanatory comment, and
    the first version of this test failed on both of them. What matters is whether
    an import statement is at module level, which is a question for the tree.
    """
    import ast

    module = importlib.import_module("pyjab.inspector")
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))

    at_module_level = []
    for node in tree.body:                       # body, not walk: only the top level
        if isinstance(node, ast.Import):
            at_module_level.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            at_module_level.append(node.module or "")

    offenders = [name for name in at_module_level
                 if name.startswith("pyjab") and name != "pyjab.common.xpathparser"]
    assert not offenders, (
        f"imported at module scope, which fails off Windows: {offenders}"
    )
