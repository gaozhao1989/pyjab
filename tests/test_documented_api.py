"""The documented-API check, and the three defects that were in the docs.

Written against the real API index rather than a fixture, because the thing being
checked is precisely whether the index matches the package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_documented_api", REPO_ROOT / "tools" / "check_documented_api.py"
)
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_documented_api"] = checker
_spec.loader.exec_module(checker)

MODULES = checker.pyjab_modules()
MEMBERS = checker.class_members(MODULES)


# ---------------------------------------------------------------------------
# Reading names out of the code
# ---------------------------------------------------------------------------

def test_a_private_name_is_not_public():
    assert not checker.is_public("_helper")
    assert not checker.is_public("find_bridge_dll".replace("find", "_find", 1))


def test_a_dunder_is_public():
    """pyjab.__version__ is documented, and exists.

    A plain "starts with an underscore" filter reports it as missing, which the
    first run of the check did.
    """
    assert checker.is_public("__version__")


def test_the_index_finds_the_classes_the_docs_name():
    for name in ("JABDriver", "JABElement", "Role", "By", "Win32Utils"):
        assert name in MEMBERS, name


def test_the_index_records_properties_as_well_as_methods():
    """The documentation writes ``element.bounds`` and ``driver.title``."""
    assert "bounds" in MEMBERS["JABElement"]
    assert "title" in MEMBERS["JABDriver"]


# ---------------------------------------------------------------------------
# Resolving a dotted path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("target", [
    "pyjab",
    "pyjab.config",
    "pyjab.config.find_bridge_dll",
    "pyjab.common.by",
    "pyjab.common.actorscheduler.ActorScheduler",
    "pyjab.jabdriver",
])
def test_a_real_path_resolves(target):
    assert checker._resolves(target, MODULES, MEMBERS), target


@pytest.mark.parametrize("target", [
    "pyjab.nothing_here",
    "pyjab.config.not_a_function",
    "pyjab.common.by.NotAnAttribute",
])
def test_an_invented_path_does_not(target):
    assert not checker._resolves(target, MODULES, MEMBERS), target


# ---------------------------------------------------------------------------
# Separating API from everything else in the prose
# ---------------------------------------------------------------------------

def test_a_url_is_not_an_api_reference():
    text = "see https://github.com/gaozhao1989/pyjab/blob/master/pyjab.md"

    assert "pyjab.md" not in checker.strip_noise(text)


def test_a_quoted_filename_is_not_an_attribute_access():
    """``element.get_screenshot_as_file("./element.png")`` names a file.

    Matching ``element.png`` inside the string was the first run's largest source
    of noise: it reported a missing attribute on JABElement for a path.
    """
    stripped = checker.strip_noise('element.get_screenshot_as_file("./element.png")')

    assert checker.VARIABLE_ATTRIBUTE.findall(stripped) == [
        ("element", "get_screenshot_as_file")
    ]


def test_a_fenced_code_block_is_not_swallowed_as_a_quoted_string():
    """Two backticks are not three.

    A quote pattern allowed to span newlines matched the first two backticks of a
    ``` fence and consumed the code inside it, which silently turned three real
    findings into a pass.
    """
    text = "```python\ndriver.get_missing_thing()\n```"

    assert "driver.get_missing_thing" in checker.strip_noise(text)


def test_a_file_suffix_is_not_a_module():
    """``pyjab.md`` is a page; ``pyjab.wiki.git`` is a repository."""
    assert "md" in checker.FILE_SUFFIXES
    assert "git" in checker.FILE_SUFFIXES


# ---------------------------------------------------------------------------
# The whole check, on a file written for it
# ---------------------------------------------------------------------------

def write_doc(tmp_path, body) -> Path:
    path = tmp_path / "probe.md"
    path.write_text(body, encoding="utf-8")
    return path


def problems_for(tmp_path, body):
    return checker.references_in(write_doc(tmp_path, body), MODULES, MEMBERS)


def test_a_missing_method_is_reported(tmp_path):
    found = problems_for(tmp_path, "```python\ndriver.get_screenshot_as_png()\n```")

    assert len(found) == 1
    line, what, why = found[0]
    assert what == "driver.get_screenshot_as_png"
    assert "JABDriver" in why


def test_a_missing_method_on_an_element_is_reported(tmp_path):
    found = problems_for(tmp_path, "element.no_such_method()")

    assert [f[1] for f in found] == ["element.no_such_method"]


def test_a_missing_class_attribute_is_reported(tmp_path):
    found = problems_for(tmp_path, "`By.NOT_A_KEY`")

    assert [f[1] for f in found] == ["By.NOT_A_KEY"]


def test_a_missing_imported_name_is_reported(tmp_path):
    found = problems_for(tmp_path, "from pyjab.jabdriver import NotAClass")

    assert [f[1] for f in found] == ["pyjab.jabdriver.NotAClass"]


def test_a_missing_module_in_an_import_is_reported(tmp_path):
    found = problems_for(tmp_path, "from pyjab.nowhere import Thing")

    assert [f[1] for f in found] == ["pyjab.nowhere"]


def test_correct_references_are_not_reported(tmp_path):
    body = (
        "```python\n"
        "from pyjab.jabdriver import JABDriver\n"
        "from pyjab.common.by import By\n"
        "\n"
        "with JABDriver(title='x') as driver:\n"
        "    driver.set_window_size(1280, 800)\n"
        "    driver.get_screenshot_as_file('window.png')\n"
        "    element = driver.find_element_by_name('A Label')\n"
        "    element.double_click()\n"
        "    width = element.bounds['width']\n"
        "    role = element.role_en_us\n"
        "    assert By.NAME == 'name'\n"
        "```\n"
        "\n"
        "See `pyjab.config`_ and https://example.com/pyjab.md\n"
    )

    assert problems_for(tmp_path, body) == []


def test_a_deliberate_reference_to_a_removed_api_is_allowable():
    """The changelog names removed APIs on purpose."""
    assert "setup_msg_pump" in checker.KNOWN_REMOVED

    # And the entry says why, rather than being a bare exemption.
    assert checker.KNOWN_REMOVED["setup_msg_pump"]


# ---------------------------------------------------------------------------
# The repository as it stands
# ---------------------------------------------------------------------------

def test_every_published_file_is_clean():
    """The end-to-end check. It failed three times when first written:

    ``driver.get_screenshot_as_png()`` and ``driver.get_screenshot_as_base64()``
    in docs/3, neither of which has ever existed, and ``driver.get_window_size()``,
    which has no counterpart to ``get_window_position()``.
    """
    failures = []
    for path in checker.documented_files():
        for number, what, why in checker.references_in(path, MODULES, MEMBERS):
            failures.append(f"{path.relative_to(REPO_ROOT)}:{number} {what} -- {why}")

    assert not failures, "\n".join(failures)


def test_the_screenshot_methods_the_docs_once_promised_do_not_exist():
    """The finding, pinned so that adding them later is a deliberate act.

    If someone adds `get_screenshot_as_base64()` this test should fail, and the
    person should then delete it and note the addition in the changelog -- which
    is the point: the docs used to promise it without anyone deciding to.
    """
    assert "get_screenshot_as_file" in MEMBERS["JABDriver"]
    assert "get_screenshot" in MEMBERS["JABDriver"]
    assert "get_screenshot_as_png" not in MEMBERS["JABDriver"]
    assert "get_screenshot_as_base64" not in MEMBERS["JABDriver"]
    assert "get_window_size" not in MEMBERS["JABDriver"]
