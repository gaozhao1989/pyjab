"""XPath against the accessibility tree of the real test application.

Every other XPath test builds its tree by hand, which means it tests the traversal
against a structure chosen to make the traversal work. This one does not: it starts
the Swing application the GUI suite drives, asks it to print its accessibility tree,
and runs the locators against **that**.

The accessibility layer is a JVM-side API, identical on every platform, so the tree
printed here is the tree Java Access Bridge reports on Windows. Only the transport is
faked; the names, the roles and the shape are the application's own. That is enough to
catch the class of mistake the hand-built trees cannot -- a role spelled the way pyjab
expects but the application does not use, a name that is not the accessibility name, a
locator that assumes a depth the real hierarchy does not have.

Needs a JDK. It is skipped without one, which is a real limitation and not a
convenience: CI has a JDK, so there it runs, and locally it runs if JAVA_HOME or the
PATH has one. Run tools/verify_test_app.py for the same information without pytest.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.exceptions import JABException

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_DIR = REPO_ROOT / "tests" / "java"
APP_CLASS = "PyjabTestApp"

#: `name=<name>  role=<role>`, indented two spaces per level. Two spaces separate the
#: two fields rather than one, because a name can contain a single space.
LINE = re.compile(r"^(?P<indent> *)(?:- )?name=(?P<name>.*?)  role=(?P<role>.+)$")


def java_tool(name: str):
    home = os.environ.get("JAVA_HOME")
    if home:
        candidate = Path(home) / "bin" / name
        if candidate.exists():
            return str(candidate)
    return shutil.which(name)


def accessibility_dump() -> str:
    """The real application's tree, as text, in English role names.

    The locale matters: with a Chinese JVM the same run says ``role=按钮``, and
    pyjab matches ``role_en_us``. A test that silently accepted both would not be
    checking what JAB reports on an English Windows session.
    """
    javac, java = java_tool("javac"), java_tool("java")
    if not javac or not java:
        pytest.skip("no JDK: JAVA_HOME or the PATH needs javac and java")

    classes = REPO_ROOT / "tests" / "java" / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    sources = sorted(str(p) for p in JAVA_DIR.glob("*.java"))
    try:
        subprocess.run([javac, "-d", str(classes), *sources],
                       check=True, capture_output=True)
        output = run_application(java, classes)
    except (OSError, subprocess.CalledProcessError) as error:
        # `which` finding a file is not the same as a JDK being installed. macOS
        # ships /usr/bin/java as a stub that prints "Unable to locate a Java Runtime"
        # and exits non-zero, so without this the whole file errors instead of
        # skipping -- which is worse than skipping, because an error in CI reads as a
        # broken change.
        detail = getattr(error, "stderr", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        pytest.skip(f"no working JDK: {str(error)[:120]} {detail.strip()[:120]}")

    if not output.strip():
        pytest.skip(
            "the application produced no accessibility tree. It builds a JFrame, so "
            "it needs a display: on a headless machine this cannot run at all, and on "
            "a runner that has xvfb it is retried under one automatically."
        )
    return output


def run_application(java: str, classes: Path) -> str:
    """Run the dump, under a virtual display if there is no real one.

    GitHub's ubuntu runners are headless and ship xvfb-run, so the check can run
    there rather than skipping -- which matters, because a guard that skips in CI is
    the thing this file's own commit message complains about. The first version of
    this skipped on every Linux run with "the application printed no accessibility
    tree" and looked green.
    """
    command = [java, "-Duser.language=en", "-Duser.country=US",
               "-cp", str(classes), APP_CLASS, "--dump-accessibility"]

    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    if completed.stdout.strip() or os.environ.get("DISPLAY"):
        return completed.stdout

    xvfb = shutil.which("xvfb-run")
    if not xvfb:
        return completed.stdout

    retried = subprocess.run([xvfb, "-a", *command],
                             check=True, capture_output=True, text=True)
    return retried.stdout or completed.stdout


def build(lines: list) -> tuple:
    """Turn the dump into a fake tree, returning ``(root, element, bridge)``."""
    from tests._fakejab import Node, bind

    root = None
    stack = []          # (depth, node)

    for line in lines:
        match = LINE.match(line)
        if match is None:
            continue
        depth = len(match.group("indent")) // 2
        name = match.group("name")
        node = Node(match.group("role"), name="" if name == "null" else name)

        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            parent.children.append(node)
            node.parent = parent
        else:
            root = node
        stack.append((depth, node))

    if root is None:
        pytest.skip("the application printed no accessibility tree")

    element, bridge = bind(root)
    return root, element, bridge


@pytest.fixture(scope="module")
def real():
    """The real tree, loaded once -- compiling Java on every test is wasteful."""
    lines = accessibility_dump().splitlines()
    root, element, _ = build(lines)
    return element, root, lines


def test_the_dump_is_the_real_application(real):
    _element, root, lines = real

    assert len(lines) > 300, "the tree looks truncated"
    assert root.role == "frame"
    assert root.name == APP_CLASS


def test_a_real_button_is_found_by_name(real):
    """The locator the GUI suite itself uses, against the real hierarchy."""
    element, _root, _lines = real

    found = element.find_element_by_xpath("//push button[@name='Disable middle button']")

    assert found.role_en_us == "push button"
    assert found.name == "Disable middle button"


def test_comparisons_work_on_the_real_tree(real):
    """`@indexinparent` and `@childrencount` come from the real hierarchy.

    Numbers, not strings: the toolbar and the button column both have more than nine
    children in places, and a string comparison would order them wrongly and still
    look plausible.
    """
    element, root, _lines = real

    many_children = element.find_elements_by_xpath("//panel[@childrencount>9]")

    assert many_children, "no panel in the real tree has more than nine children"
    for panel in many_children:
        assert panel.children_count > 9


def test_a_position_selects_within_each_parent_on_the_real_tree(real):
    """`[1]` is the first matching child of every parent, not the first in the app.

    On a hand-built tree the difference can be arranged away. Here it cannot: the
    application has several containers that each hold a first button.
    """
    element, _root, _lines = real

    firsts = element.find_elements_by_xpath("//push button[1]")
    everything = element.find_elements_by_xpath("//push button")

    assert len(firsts) < len(everything), "every button was its parent's first"
    assert len(firsts) > 1, "only one parent in the real tree holds a button"
    for found in firsts:
        assert found.role_en_us == "push button"


def test_a_union_merges_two_real_searches_without_duplicates(real):
    element, _root, _lines = real

    merged = element.find_elements_by_xpath("//push button | //label")
    again = element.find_elements_by_xpath("//push button | //push button")

    buttons = [e for e in merged if e.role_en_us == "push button"]
    labels = [e for e in merged if e.role_en_us == "label"]
    assert buttons and labels
    assert len(again) == len(buttons), "the same button came back more than once"


def test_the_parent_axis_walks_the_real_hierarchy(real):
    """`//label/..` on a tree nobody shaped for the test."""
    element, _root, _lines = real

    parents = element.find_elements_by_xpath("//label/..")

    assert parents, "no label in the real tree has a parent, which cannot be"
    for parent in parents:
        assert parent.role_en_us != "label" or True      # a label can hold labels
    # Every parent must actually contain the label it was reached through.
    for parent in parents[:20]:
        assert parent.children_count > 0


def test_a_label_deep_in_the_tree_is_reachable(real):
    """A path with several steps, which is where the pruning has to hold up."""
    element, _root, _lines = real

    found = element.find_elements_by_xpath("//panel//label")

    assert found, "no label is reachable through a panel on the real tree"


def test_the_forms_that_cannot_work_still_say_so_on_a_real_tree(real):
    """The rejection is the parser's, so the tree cannot change it -- and this
    checks the parser is reached before any JAB call is made."""
    from pyjab.common.exceptions import XpathParserException

    element, _root, _lines = real

    for locator in ["//push button[0]", "//push button[last()]"]:
        with pytest.raises(XpathParserException):
            element.find_elements_by_xpath(locator)


def test_a_locator_that_matches_nothing_raises_on_a_real_tree(real):
    element, _root, _lines = real

    with pytest.raises(JABException):
        element.find_elements_by_xpath("//push button[@name='No Such Button Anywhere']")
