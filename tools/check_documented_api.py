#!/usr/bin/env python
"""Check that every pyjab API the documentation names actually exists.

Why this exists
---------------
The working agreement already says to confirm an API exists before citing it, in
documentation, tests, scripts and issue replies alike. That rule was being kept
by hand, which means it was kept until someone was in a hurry.

It is worth mechanising because the failure is invisible in the direction that
matters. A missing method in a test fails the suite; a missing method in the
README fails nothing, and the first person to find out is a user who copied the
example. Two were in the documentation when this was written -- documented
`driver.get_screenshot_as_png()` and `driver.get_screenshot_as_base64()`, neither
of which has ever existed -- and one was in a docstring inside the package.

What it checks
--------------
* every ``pyjab.<dotted.path>`` in the prose resolves;
* every ``from pyjab... import X`` and ``import pyjab...`` resolves;
* every ``Class.attribute`` where the class is one of pyjab's resolves;
* ``driver.`` and ``element.``, which are the two names the documentation uses
  consistently for a :class:`JABDriver` and a :class:`JABElement`.

Usage
-----
    python tools/check_documented_api.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Maintainer notes, not published documentation.
INTERNAL_NOTES = frozenset({
    "TRIAGE.md", "ROADMAP.md", "PYJAB_MCP_PLAN.md", "ISSUE_REPLIES.md",
    "CONSENT_REQUESTS.md",
})

#: The variable names the documentation uses, and what they hold.  Short and
#: explicit rather than inferred: inferring a variable's class from its
#: construction inside a code block would be cleverer and would also silently
#: stop checking anything the day the examples change shape.
DOCUMENTED_VARIABLES = {
    "driver": "JABDriver",
    "element": "JABElement",
    "test_app": "JABDriver",
    "form_textfield": "JABElement",
    "from_textfield": "JABElement",
    "app": "JABDriver",
    # `table` and `cell` are JABElements in the examples.  Leaving them out is not
    # neutral: the whole Tables section went unchecked, so it passed while naming
    # methods that did not exist, which is the failure this tool exists to catch.
    "table": "JABElement",
    "cell": "JABElement",
    # Names used by the verification scripts, which hold JABElements they found by
    # xpath. Without these the check silently skips every attribute access in
    # tools/verify_xpath.py, because they are not called `element`.
    "button": "JABElement",
    "buttons": "JABElement",
    "target": "JABElement",
    "disable": "JABElement",
    "parents": "JABElement",
    "named": "JABElement",
    "merged": "JABElement",
    "firsts": "JABElement",
    "twice": "JABElement",
    "every": "JABElement",
}

#: Names that are deliberately absent from the code, with the reason.  A
#: reference to a removed API is legitimate in the changelog and the upgrade
#: notes, which exist to describe what was removed -- so it is listed here rather
#: than the check being loosened until it stops noticing anything.
KNOWN_REMOVED = {
    "setup_msg_pump": "removed in 1.3.0; named only in the upgrade notes",
    # Removed in 2.0.0. It returned a Pillow ``Image``, which made Pillow a runtime
    # dependency for one convenience method -- and a method that was pyjab's own
    # divergence rather than something Selenium users expect (Selenium's returns base64).
    # The screenshot API is otherwise unchanged and needs no third-party package;
    # ``Image.open(BytesIO(driver.get_screenshot_as_png()))`` is the same thing in one
    # line, on the caller's side, where that dependency belongs.
    "get_screenshot": "removed in 2.0.0; use get_screenshot_as_png with an image library",
}

#: ``pyjab.something.else`` in prose.  URLs are excluded below, because a link to
#: ``github.com/.../pyjab.md`` is not a reference to a module.
PYJAB_PATH = re.compile(r"\bpyjab(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
FROM_IMPORT = re.compile(r"^\s*from\s+(pyjab[\w.]*)\s+import\s+(.+)$")
IMPORT = re.compile(r"^\s*import\s+(pyjab[\w.]*)")
CLASS_ATTRIBUTE = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)")
VARIABLE_ATTRIBUTE = re.compile(
    r"\b(" + "|".join(DOCUMENTED_VARIABLES) + r")\.([A-Za-z_][A-Za-z0-9_]*)"
)
URL = re.compile(r"https?://\S+|\bgithub\.com/\S+|\bpypi\.org/\S+")

#: Quoted text, which is data rather than API.  ``element.get_screenshot_as_file``
#: takes a filename, and a filename ending in ``.png`` used to be read as an
#: attribute access on ``element``.
#: Nothing here may span a newline.  A pattern that does would match the first
#: two backticks of a fenced block and swallow the code inside it -- which is how
#: three real defects went unreported for one run.
QUOTED = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'|``[^`\n]*``')

#: A dotted name that ends in a file extension is a file, not a module --
#: ``pyjab.md`` is a page in this repository, and ``pyjab.wiki.git`` is a
#: repository. Neither is an attribute of the package.
FILE_SUFFIXES = (
    "md", "rst", "txt", "py", "pyc", "png", "jpg", "json", "toml", "cfg",
    "ini", "yml", "yaml", "zip", "gz", "tar", "git", "html", "pdf", "sh",
)


def documented_files() -> list:
    """Every published file that quotes the API."""
    found = []
    for name in ("README.rst", "CONTRIBUTING.rst"):
        path = REPO_ROOT / name
        if path.is_file():
            found.append(path)
    for path in sorted((REPO_ROOT / "docs").glob("*.md")):
        if path.name not in INTERNAL_NOTES:
            found.append(path)
    return found


# ---------------------------------------------------------------------------
# The API, read out of the code
# ---------------------------------------------------------------------------

def pyjab_modules() -> dict:
    """Every module under pyjab/, keyed by its dotted path."""
    modules = {}
    for path in sorted((REPO_ROOT / "pyjab").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        modules[".".join(parts)] = path
    return modules


def is_public(name: str) -> bool:
    """A name a reader may use: not private, but dunders included.

    ``pyjab.__version__`` is documented and exists, so a plain "starts with an
    underscore" filter reports it as missing -- which the first run did.
    """
    if name.startswith("__") and name.endswith("__"):
        return True
    return not name.startswith("_")


def module_attributes(path: Path) -> set:
    """The public names a module defines: classes, functions and assignments."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if is_public(node.name):
                names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and is_public(target.id):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if is_public(node.target.id):
                names.add(node.target.id)
    return names


def class_members(modules: dict) -> dict:
    """Public attributes of every class pyjab defines, keyed by class name.

    Properties count: the documentation calls ``element.bounds`` and
    ``element.text`` without brackets, and both are properties.
    """
    members = {}
    for path in modules.values():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            found = set()
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if is_public(child.name):
                        found.add(child.name)
                elif isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and is_public(target.id):
                            found.add(target.id)
            # Attributes assigned to self inside a method count as well.
            # JABDriver sets self.win32utils in __init__, and a version that
            # looked only at the class body reported it as missing -- a false
            # positive that would have failed this check on correct code.
            for item in ast.walk(node):
                target = None
                if isinstance(item, ast.Assign):
                    for candidate in item.targets:
                        if (isinstance(candidate, ast.Attribute)
                                and isinstance(candidate.value, ast.Name)
                                and candidate.value.id == "self"):
                            target = candidate.attr
                elif (isinstance(item, ast.AnnAssign)
                      and isinstance(item.target, ast.Attribute)
                      and isinstance(item.target.value, ast.Name)
                      and item.target.value.id == "self"):
                    target = item.target.attr
                if target and is_public(target):
                    found.add(target)
            members.setdefault(node.name, set()).update(found)
    return members


# ---------------------------------------------------------------------------
# The references, read out of the documentation
# ---------------------------------------------------------------------------

def blank(match) -> str:
    """Replace a match with spaces, keeping every other column where it was."""
    return " " * len(match.group(0))


def strip_noise(text: str) -> str:
    """Blank out URLs and quoted strings, keeping the line numbers intact."""
    return QUOTED.sub(blank, URL.sub(blank, text))


def package_files() -> list:
    """Every module in the package, whose docstrings are read as well.

    A docstring is documentation.  The three methods the documentation promised
    and never had were found in README and docs/ -- but when those were fixed, a
    fourth turned up inside `JABElement.get_screenshot_as_file`, whose example
    called an `element.screenshot()` that has never existed either.  Nothing was
    reading the package's own prose.
    """
    return sorted((REPO_ROOT / "pyjab").rglob("*.py"))


#: What a script calls a JABDriver or a JABElement.  Separate from
#: DOCUMENTED_VARIABLES because scripts use different words for the same things,
#: and adding them there would change what the documentation check reports.
TOOL_VARIABLES = {
    "driver": "JABDriver",
    "app": "JABDriver",
    "jab": "JABDriver",
    "test_app": "JABDriver",
    "element": "JABElement",
    "el": "JABElement",
    "table": "JABElement",
    "cell": "JABElement",
}


def tool_files() -> list:
    """Every script in tools/, whose attribute accesses are checked as well.

    AGENTS.md 1.1 says to confirm an API exists before citing it "in
    documentation, tests, scripts and issue replies alike", and calls it
    mechanical.  This check did the documentation and the package docstrings and
    stopped there, so the scripts went unread -- and ``tools/verify_dpi.py``
    reached ``driver.win32_utils``, which does not exist.  ``JABDriver`` names it
    ``win32utils``; ``JABElement`` names it ``win32_utils``.  The script used the
    element's spelling on the driver.

    Nobody could have caught it by reading here: it compiles, it imports, and it
    runs until the one machine that can execute it -- Windows, with a JDK, at the
    point of the decisive click, after the measurements had already been taken.
    That is the whole argument for checking it rather than finding it.
    """
    return sorted((REPO_ROOT / "tools").glob("*.py"))


def tool_references(path: Path, members: dict) -> list:
    """Attribute accesses in one script that the class does not have.

    Only for the variable names in TOOL_VARIABLES.  A script that calls its driver
    something else is not checked, which is a gap -- and the cost of closing it
    with a guess is a false positive that makes the check untrustworthy, which is
    worse than a gap.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Name):
            continue
        class_name = TOOL_VARIABLES.get(node.value.id)
        if class_name is None:
            continue
        if node.attr.startswith("__"):
            continue
        if node.attr not in members.get(class_name, set()):
            problems.append((
                node.lineno,
                f"{node.value.id}.{node.attr}",
                f"{node.value.id} is a {class_name}, which has no such attribute",
            ))
    return problems


def docstrings_in(path: Path) -> list:
    """Every docstring in a module, as ``(line, text)``.

    The line number is where the docstring's *content* starts, so a finding
    points at the sentence rather than at the ``def`` above it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring is None:
            continue
        # The node's first statement holds the string; count from its own line.
        body = getattr(node, "body", None)
        if not body or not isinstance(body[0], ast.Expr):
            continue
        start = body[0].value.lineno
        found.append((start, docstring))
    return found


def references_in(path: Path, modules: dict, members: dict) -> list:
    """Every API reference in one file, as ``(line, what, problem)``.

    A module is read for its docstrings rather than for its code: the code's own
    attribute accesses are checked by the test suite, whereas a docstring is
    prose that nothing else looks at.
    """
    if path.suffix == ".py":
        lines = []
        for start, docstring in docstrings_in(path):
            for offset, line in enumerate(strip_noise(docstring).splitlines()):
                lines.append((start + offset, line))
    else:
        text = strip_noise(path.read_text(encoding="utf-8"))
        lines = list(enumerate(text.splitlines(), start=1))

    problems = []
    for number, line in lines:
        for match in PYJAB_PATH.finditer(line):
            target = match.group(0)
            if target.rsplit(".", 1)[-1] in FILE_SUFFIXES:
                continue
            if not _resolves(target, modules, members):
                problems.append((number, target, "no such module or attribute"))

        from_match = FROM_IMPORT.match(line)
        plain_match = IMPORT.match(line)
        if from_match:
            module, names = from_match.group(1), from_match.group(2)
            if module not in modules:
                problems.append((number, module, "no such module"))
            else:
                available = module_attributes(modules[module])
                for name in (n.strip().split(" as ")[0] for n in names.split(",")):
                    if name and name != "*" and name not in available:
                        problems.append(
                            (number, f"{module}.{name}", "not defined there"))
        elif plain_match:
            module = plain_match.group(1)
            if module not in modules:
                problems.append((number, module, "no such module"))

        for match in CLASS_ATTRIBUTE.finditer(line):
            class_name, attribute = match.groups()
            if class_name in members and attribute not in members[class_name]:
                if attribute in KNOWN_REMOVED:
                    continue
                problems.append(
                    (number, f"{class_name}.{attribute}",
                     f"{class_name} has no such attribute"))

        for match in VARIABLE_ATTRIBUTE.finditer(line):
            variable, attribute = match.groups()
            class_name = DOCUMENTED_VARIABLES[variable]
            if class_name in members and attribute not in members[class_name]:
                if attribute in KNOWN_REMOVED:
                    continue
                problems.append(
                    (number, f"{variable}.{attribute}",
                     f"{variable} is a {class_name}, which has no such attribute"))

    # An import line is matched by the path scan as well, so
    # `from pyjab.nowhere import Thing` came out twice. Once per line and name.
    seen = set()
    unique = []
    for entry in problems:
        key = (entry[0], entry[1])
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def _resolves(target: str, modules: dict, members: dict) -> bool:
    """Whether ``pyjab.a.b`` names something that exists."""
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        candidate = ".".join(parts[:cut])
        if candidate in modules:
            rest = parts[cut:]
            if not rest:
                return True
            # Walk the remainder through the module's names, then the class
            # attributes, treating anything unrecognised as a failure.
            names = module_attributes(modules[candidate])
            if rest[0] not in names:
                return False
            current = rest[0]
            for name in rest[1:]:
                if current in members and name in members[current]:
                    continue
                return False
            return True
    return False


def main() -> int:
    modules = pyjab_modules()
    members = class_members(modules)

    files = documented_files() + package_files()
    tools = tool_files()
    total = 0
    failures = 0

    print("documentation and package docstrings")
    for path in files:
        problems = references_in(path, modules, members)
        total += 1
        failures += report(path, problems)

    print("\nscripts")
    for path in tools:
        problems = tool_references(path, members)
        total += 1
        failures += report(path, problems)

    print(f"\nchecked {total} file(s) -- published documentation, the package's own "
          f"docstrings,\nand tools/ --\nagainst {len(modules)} modules and "
          f"{len(members)} classes")

    if failures:
        print(f"\nFAILED: {failures} reference(s) name something that does not exist.")
        print(
            "\n  Either the code lost an API something still uses, or the reference\n"
            "  was invented. Both are worth knowing about before it is run. If the\n"
            "  reference is deliberate -- a changelog describing something removed\n"
            "  -- add the name to KNOWN_REMOVED in this script with the reason."
        )
        return 1

    print("\nPASSED: every API the documentation and the tools name exists.")
    return 0


def report(path: Path, problems: list) -> int:
    """Print one file's findings, and say how many there were."""
    relative = path.relative_to(REPO_ROOT).as_posix()
    for number, what, why in problems:
        print(f"  {relative}:{number}  {what}  -- {why}")
    return len(problems)


if __name__ == "__main__":
    sys.exit(main())
