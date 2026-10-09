"""Every XPath example in the documentation has to actually parse.

`docs/3-pyjab.md` claimed `[n]` positional predicates were supported. They are
not, and never were: `get_node_attributes` only recognises `@name=value`, so a
bare `[1]` raises. The test suite knew -- `tests/test_xpath_parser.py` lists
`panel[1]` among the nodes that must be *rejected* -- and the documentation said
the opposite, for long enough that the tracking issue listed it as done.

Nothing connected the two, which is what this does. It reads the examples out of
the documentation and asks the parser about each one. It cannot tell whether a
locator will *match* anything -- that depends on the application -- but it can
tell whether the syntax in the manual is syntax pyjab accepts, and that is the
half that was wrong.

The reverse direction is not checked and cannot be: pyjab accepting something the
documentation does not mention is not a defect, it is an undocumented feature.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _win32stubs  # noqa: F401  -- installs the pywin32 stand-ins on import
from pyjab.common.exceptions import XpathParserException
from pyjab.common.xpathparser import XpathParser

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = [REPO_ROOT / "docs" / "3-pyjab.md", REPO_ROOT / "README.rst"]

parser = XpathParser.__wrapped__()


def xpath_examples(path: Path) -> list:
    """XPath-looking lines from the fenced blocks and inline code in *path*.

    The documentation's example blocks align a description beside each locator::

        //panel                          any panel, anywhere

    so the first whitespace-separated word of a line is the whole locator and
    everything after it is prose.  A bare ``//`` or ``.//`` is the axis being
    named in a sentence rather than a locator, and is skipped.
    """
    text = path.read_text(encoding="utf-8")
    fenced = re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL)
    inline = re.findall(r"`([^`\n]+)`", text)
    examples = set()
    for block in list(fenced) + list(inline):
        for line in block.splitlines():
            # Two or more spaces separate a locator from its description: the
            # locators themselves contain single spaces ("//push button").
            token = re.split(r"\s{2,}", line.strip())[0].strip()
            if not token.startswith(("//", ".//")):
                continue
            if token in ("//", ".//"):
                continue
            examples.add(token)
    return sorted(examples)


def parses(xpath: str) -> bool:
    """Instance calls, not class ones, and that is not style.

    ``split_nodes`` is a staticmethod on a class that ``@singleton`` replaces with
    a function, and ``functools.wraps`` copies the class dictionary onto that
    wrapper -- where a ``staticmethod`` object is **not callable on Python 3.9**.
    ``XpathParser.split_nodes(...)`` therefore works on 3.10 and up and raises
    ``TypeError`` on 3.9, which is how the first version of this file failed all
    three py3.9 CI jobs. The same trap is recorded in ``pyjab/jabfixedfunc.py``
    for ``double_click_gap``.
    """
    try:
        # Unions first: `//a | //b` is two paths, and split_nodes would treat the `|`
        # as part of a role name. This is the check that caught the omission -- it
        # failed on the union examples the moment they were added to the docs.
        for branch in parser.split_union(xpath):
            for node in parser.split_nodes(branch):
                parser.get_node_information(node)
    except XpathParserException:
        return False
    return True


@pytest.mark.parametrize("path", DOCS, ids=lambda p: p.name)
def test_the_examples_are_syntax_this_parser_accepts(path):
    broken = [x for x in xpath_examples(path) if not parses(x)]

    assert not broken, (
        f"{path.name} shows XPath that pyjab rejects:\n  "
        + "\n  ".join(broken)
    )


def test_the_check_would_notice_a_wrong_example():
    """Guards the guard: a documented example that does not parse must fail.

    Without this, a pattern that matched nothing would let the test pass for ever
    while checking nothing at all -- which is the failure this file exists to
    catch, one level up.
    """
    assert parses("//panel[@name='x']")
    assert parses("//panel[1]"), "[n] is supported now; it was not before 1.8.0"
    assert parses("//panel[@indexinparent > 10]"), "comparisons work as of this release"
    assert not parses("//panel/../panel"), "the parent axis is still rejected"


def test_the_examples_are_actually_found():
    """And that there is something to check in the first place."""
    found = xpath_examples(DOCS[0])

    assert len(found) >= 6, f"only found {found}"
    assert any("contains(" in x for x in found)
    assert any("@" in x for x in found), "predicates are documented"
    assert any("/" in x[len(x.split("/", 2)[0]):] for x in found), (
        "a multi-step path is documented"
    )


def test_the_relative_form_is_documented_even_though_it_is_not_extracted():
    """`.//x` appears inside a Python call, so the extractor cannot see it.

    Said here rather than left implicit: the extractor picks up locators that are
    a line on their own, and the relative form is only ever shown in context. If
    it stopped being documented at all, the examples above would still pass.
    """
    text = (REPO_ROOT / "docs" / "3-pyjab.md").read_text(encoding="utf-8")

    assert '".//push button"' in text
    assert "from this element" in text
