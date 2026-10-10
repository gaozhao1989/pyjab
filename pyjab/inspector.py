"""``pyjab-inspect`` -- find out what is actually in a Java window.

The problem this exists for is #75: a control cannot be found, and there is nothing
to look at. ``find_element_by_name("Save")`` raises "no JABElement found", which is
true and useless -- it does not say whether the window is the wrong one, the name is
spelled differently, the role is not what you assumed, or the element is there but
nested somewhere you did not expect.

Three commands answer those in order:

``pyjab-inspect windows``
    Which Java windows JAB can see at all. If the application is not in this list,
    nothing else will work and the problem is the attachment, not the locator.

``pyjab-inspect tree <title>``
    What is in the window: role, name and the attributes a locator can use, indented
    by depth. This is the view that turns guessing into reading.

``pyjab-inspect find <title> <xpath>``
    Whether a locator resolves, and when it does not, **which step stopped**. A path
    is a sequence of steps and only one of them is usually wrong; reporting the
    prefix that went from *n* matches to zero says which.

``pyjab-inspect locator <title> --name Save``
    The reverse: given part of a name or role, print locators that resolve right now,
    ready to paste.

Built into the package rather than left in ``tools/`` because that is where users can
reach it: the wheel contains only ``pyjab``, so a script under ``tools/`` ships in the
sdist and never arrives with ``pip install pyjab``.

Windows only, like the rest of pyjab. ``pyjab.jabdriver`` is imported inside the
functions so that this module -- and its argument handling and formatting, which are
the parts worth testing -- can be imported anywhere.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys

__all__ = [
    "main",
    "build_parser",
    "render_tree",
    "suggest_locators",
    "step_report",
]

#: Quoted for an xpath literal; a name containing the quote being used gets the other
#: one, and a name containing both cannot be expressed and is reported instead.
def _quote(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    raise ValueError(f"the name contains both quote characters: {value!r}")


def record(element) -> dict:
    """This element as plain data. See :meth:`pyjab.jabelement.JABElement.as_record`."""
    return element.as_record()


def walk(element, max_depth: int, limit: int):
    """Walk a subtree, yielding ``(depth, record)``.

    Delegates to :meth:`pyjab.jabelement.JABElement.walk`, which is where this now lives:
    traversal is a thing an element can do, and the CLI is only its first caller. It moved
    because a second project needed it and a private function in a CLI module is not
    something another project may depend on.

    The return value is a ``JABTree``, so the caller can ask whether the walk was
    truncated -- which this function used to make impossible, because a bare generator has
    nowhere to put that answer.
    """
    return element.walk(max_depth=max_depth, limit=limit)


def render_tree(entries, show_bounds: bool = False) -> str:
    """The tree as text, one line per element, indented by depth.

    Columns rather than a flat sentence because the question being answered is
    usually "why did my locator not match", which is a comparison between what the
    locator says and what is here.
    """
    lines = []
    for depth, item in entries:
        name = item["name"] or "(unnamed)"
        row = (
            f"{'  ' * depth}{item['role']}  name={name!r}"
            f"  idx={item['index_in_parent']}  children={item['children_count']}"
            f"  depth={item['object_depth']}"
        )
        if item["states"]:
            row += f"  states={item['states']}"
        if show_bounds and item["bounds"]:
            b = item["bounds"]
            row += (
                f"  bounds=({b.get('x')},{b.get('y')}"
                f",{b.get('width')}x{b.get('height')})"
            )
        lines.append(row)
    return "\n".join(lines)


def suggest_locators(item: dict, siblings: int = 1) -> list:
    """Locators that would find this element, most specific first.

    Ordered by what survives a change in the application. A name is stable; an index
    is not, so it is offered last and only when the name is not unique among the
    element's siblings.
    """
    role = item["role"]
    name = item["name"]
    candidates = []

    if name:
        candidates.append(f"//{role}[@name={_quote(name)}]")
        if item["description"]:
            candidates.append(f"//{role}[@description={_quote(item['description'])}]")
    if siblings > 1 and item["index_in_parent"] is not None:
        if name:
            candidates.append(
                f"//{role}[@name={_quote(name)}][@indexinparent="
                f"{item['index_in_parent']}]"
            )
        candidates.append(
            f"//{role}[@indexinparent={item['index_in_parent']}]"
        )
    if not candidates:
        candidates.append(f"//{role}")
    return candidates


def step_report(driver, value: str, visible: bool = False) -> list:
    """Resolve a locator one step at a time, reporting where it stops.

    A path is a sequence of steps and usually only one is wrong. Running each prefix
    shows the count go *n* -> 0 at exactly that step, which turns "no element found"
    into "the third step is the problem".

    Prefixes are rebuilt from the parsed nodes rather than by trimming the string, so
    a `/` or a `[` inside a quoted attribute value cannot be mistaken for a separator.
    """
    from pyjab.common.exceptions import JABException, XpathParserException
    from pyjab.common.xpathparser import XpathParser

    relative = value.startswith(".")
    body = value[1:] if relative else value
    parser = XpathParser.__wrapped__()
    try:
        nodes = []
        for branch in parser.split_union(body):
            nodes.extend(parser.split_nodes(branch))
        # Parse every node, not just split the path.  A predicate that cannot be
        # understood -- `[last()]`, `[position()=2]` -- is a syntax error in the
        # locator, and finding it here rather than at the first prefix that happens
        # to contain it means nothing is asked of JAB and the answer says what is
        # actually wrong.  Reporting it as "0 matches at step 2" would be the exact
        # confusion this command exists to remove.
        for node in nodes:
            parser.get_node_information(node)
    except XpathParserException as exc:
        return [{"step": value, "count": None, "error": str(exc)}]

    report = []
    for index in range(len(nodes)):
        prefix = ("." if relative else "") + "//" + "/".join(nodes[: index + 1])
        try:
            matches = driver.find_elements_by_xpath(prefix, visible=visible)
            report.append({"step": prefix, "count": len(matches), "error": None})
        except JABException:
            report.append({"step": prefix, "count": 0, "error": None})
        except XpathParserException as exc:
            report.append({"step": prefix, "count": None, "error": str(exc)})
    return report


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def attached(title: str, timeout: int, launch: str):
    """A bound driver, and the application killed only if we started it.

    ``JABDriver.__exit__`` terminates the bound Java process by pid -- that is what
    makes ``with JABDriver(...)`` clean up after itself. It is the wrong thing to do
    to an application the user already had running, so the exit is skipped unless
    ``--launch`` was given. Attaching and then killing the user's own window would be
    a memorable first impression for a tool whose whole job is looking around.
    """
    from pyjab.jabdriver import JABDriver

    driver = JABDriver(title=title, file_path=launch, timeout=timeout)
    try:
        yield driver
    finally:
        if launch:
            driver.__exit__(None, None, None)


def bridge_without_window():
    """A loaded, armed bridge with no window bound to it.

    The same sequence ``init_jab`` runs, minus the window: load the DLL, arm it, pump
    once so COM events have a thread to arrive on, and register the prototypes.

    The registration is not optional. ``isJavaWindow`` takes an HWND, and without
    argtypes ctypes masks it to a C int -- so on 64-bit Windows the answer would be
    about a truncated handle, which is silently a different window. See AGENTS.md 2.8.
    """
    from pyjab.common.service import Service
    from pyjab.common.win32utils import Win32Utils
    from pyjab.jabfixedfunc import JABFixedFunc

    service = Service()
    bridge = service.load_library()
    bridge.Windows_run()
    Win32Utils().pump_messages()
    JABFixedFunc(bridge)._fix_bridge_functions()
    return bridge


def pid_of(hwnd):
    try:
        import win32process
    except ImportError:                                  # pragma: no cover - Windows
        return None
    try:
        return win32process.GetWindowThreadProcessId(hwnd)[1]
    except Exception:                                    # pragma: no cover
        return None


def cmd_windows(args) -> int:
    from pyjab.common.win32utils import Win32Utils

    bridge = bridge_without_window()
    found = []
    for hwnd, title in Win32Utils().enum_windows().items():
        if not title:
            continue
        try:
            if not bridge.isJavaWindow(hwnd):
                continue
        except Exception:                                # pragma: no cover - JAB
            continue
        found.append({"hwnd": hwnd, "title": title, "pid": pid_of(hwnd)})

    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0
    if not found:
        print("No Java windows found.")
        print(
            "\nJAB sees nothing, so no locator can work yet. Check that the "
            "application is\nrunning and is a Java window, and that Java Access "
            "Bridge is enabled -- pyjab\nwrites ~/.accessibility.properties on first "
            "use if it is not."
        )
        return 1
    print(f"{len(found)} Java window(s):")
    for item in found:
        suffix = f"  pid={item['pid']}" if item["pid"] else ""
        print(f"  hwnd={item['hwnd']}{suffix}  title={item['title']!r}")
    print("\nPass one of those titles to `tree`, `find` or `locator`.")
    return 0


def cmd_tree(args) -> int:
    with attached(args.title, args.timeout, args.launch) as driver:
        root = driver.root_element
        tree = walk(root, args.depth, args.limit)
        entries = list(tree)
        if args.json:
            print(json.dumps([{"depth": d, **item} for d, item in entries],
                             ensure_ascii=False, indent=2))
        else:
            print(f"{len(entries)} element(s) under {args.title!r}:\n")
            print(render_tree(entries, show_bounds=args.bounds))
            if tree.truncated:
                # Asked of the walk rather than inferred from the count: a tree that
                # genuinely ends at exactly --limit is not the same as one that was cut
                # off there, and only the walk knows which happened.
                print(f"\n(stopped at --limit {args.limit}; more elements follow)")
    return 0


def cmd_find(args) -> int:
    with attached(args.title, args.timeout, args.launch) as driver:
        report = step_report(driver, args.xpath, visible=args.visible)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"resolving {args.xpath!r} in {args.title!r}:\n")
            for item in report:
                if item["error"]:
                    print(f"  {item['step']}\n      parse error: {item['error']}")
                else:
                    print(f"  {item['step']}\n      {item['count']} match(es)")
            stopped = [i for i, item in enumerate(report)
                       if item["count"] == 0 or item["error"]]
            if stopped:
                first = report[stopped[0]]
                print(f"\nNothing resolved at: {first['step']}")
                if stopped[0] > 0:
                    print(f"The step before it had {report[stopped[0] - 1]['count']} "
                          f"match(es), so the problem is that step.")
            else:
                print(f"\nResolved. {report[-1]['count']} match(es) at the full path.")
    return 0 if not any(i["count"] == 0 or i["error"] for i in report) else 1


def cmd_locator(args) -> int:
    with attached(args.title, args.timeout, args.launch) as driver:
        candidates = driver.find_elements_by_role(args.role) if args.role else None
        if candidates is None:
            entries = [(d, item) for d, item in walk(driver.root_element, None, None)]
            candidates = []
            wanted = args.name
            for _depth, item in entries:
                if wanted and wanted.lower() not in item["name"].lower():
                    continue
                candidates.append(item)
        else:
            candidates = [
                item for item in (record(c) for c in candidates)
                if not args.name or args.name.lower() in item["name"].lower()
            ]

        if not candidates:
            print(f"Nothing matched role={args.role!r} name={args.name!r}.")
            print("\nTry `pyjab-inspect tree` to see what is there.")
            return 1

        print(f"{len(candidates)} candidate(s); locators that resolve now:\n")
        for item in candidates[: args.limit]:
            for locator in suggest_locators(item):
                print(f"  {locator}")
            print(f"      ({item['role']} name={item['name']!r} "
                  f"idx={item['index_in_parent']})\n")
        return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyjab-inspect",
        description="Find out what is in a Java window, and why a locator does not "
                    "resolve.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub, title_required=True):
        if title_required:
            sub.add_argument("title", help="window title, as `windows` prints it")
        sub.add_argument("--timeout", type=int, default=30,
                         help="how long to wait for the window (default 30s)")
        sub.add_argument("--launch", default=None,
                         help="path to a jar or class to start first")
        sub.add_argument("--json", action="store_true",
                         help="machine-readable output")

    windows = subparsers.add_parser("windows", help="list the Java windows JAB can see")
    windows.add_argument("--json", action="store_true")
    windows.set_defaults(func=cmd_windows)

    tree = subparsers.add_parser("tree", help="dump the accessibility tree")
    common(tree)
    tree.add_argument("--depth", type=int, default=None,
                      help="stop below this depth (default: no limit)")
    tree.add_argument("--limit", type=int, default=None,
                      help="stop after this many elements")
    tree.add_argument("--bounds", action="store_true",
                      help="include each element's rectangle")
    tree.set_defaults(func=cmd_tree)

    find = subparsers.add_parser("find", help="resolve a locator, step by step")
    common(find)
    find.add_argument("xpath", help="the locator to resolve")
    find.add_argument("--visible", action="store_true",
                      help="only consider elements that are on screen")
    find.set_defaults(func=cmd_find)

    locator = subparsers.add_parser(
        "locator", help="print locators for elements that match")
    common(locator)
    locator.add_argument("--name", default=None,
                         help="substring of the accessibility name")
    locator.add_argument("--role", default=None,
                         help="accessibility role, e.g. 'push button'")
    locator.add_argument("--limit", type=int, default=10,
                         help="how many candidates to print (default 10)")
    locator.set_defaults(func=cmd_locator)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ImportError as exc:
        # Caught around the dispatch rather than checked up front: every subcommand
        # reaches pywin32 or pythoncom somewhere, including `windows`, which needs no
        # driver but does need the bridge. A check that has to be kept in step with
        # each new subcommand will eventually be wrong for one of them, and the
        # failure is a traceback where a sentence belongs.
        print(f"pyjab-inspect needs Windows.\n\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":                                     # pragma: no cover
    sys.exit(main())
