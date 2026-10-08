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
}

#: Names that are deliberately absent from the code, with the reason.  A
#: reference to a removed API is legitimate in the changelog and the upgrade
#: notes, which exist to describe what was removed -- so it is listed here rather
#: than the check being loosened until it stops noticing anything.
KNOWN_REMOVED = {
    "setup_msg_pump": "removed in 1.3.0; named only in the upgrade notes",
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


def references_in(path: Path, modules: dict, members: dict) -> list:
    """Every API reference in one file, as ``(line, what, problem)``."""
    problems = []
    text = strip_noise(path.read_text(encoding="utf-8"))

    for number, line in enumerate(text.splitlines(), start=1):
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

    files = documented_files()
    total = 0
    failures = 0

    for path in files:
        problems = references_in(path, modules, members)
        total += 1
        if not problems:
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        for number, what, why in problems:
            print(f"  {relative}:{number}  {what}  -- {why}")
            failures += 1

    print(f"\nchecked {total} published file(s), {len(modules)} modules, "
          f"{len(members)} classes")

    if failures:
        print(f"\nFAILED: {failures} reference(s) name something that does not exist.")
        print(
            "\n  Either the code lost an API the documentation still promises, or\n"
            "  the documentation invented one. Both are worth knowing about before\n"
            "  a reader copies it. If the reference is deliberate -- a changelog\n"
            "  describing something removed -- add the name to KNOWN_REMOVED in\n"
            "  this script with the reason."
        )
        return 1

    print("\nPASSED: every API the documentation names exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
