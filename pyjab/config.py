"""Configuration and Java Access Bridge DLL discovery for :mod:`pyjab`.

The Java Access Bridge (JAB) ships a native library named
``WindowsAccessBridge-<bitness>.dll``.  Its location changed between JDK
releases:

===============  ============================================================
JDK version      DLL location
===============  ============================================================
JDK 8 - 10       ``%JAVA_HOME%\\jre\\bin\\WindowsAccessBridge-64.dll``
JDK 11 and newer ``%JAVA_HOME%\\bin\\WindowsAccessBridge-64.dll``
                 (the bundled ``jre`` directory was removed in JDK 11)
Standalone JAB   ``%JAB_HOME%\\WindowsAccessBridge-64.dll``
===============  ============================================================

Before 1.2.0, :mod:`pyjab` only ever probed ``%JAVA_HOME%\\jre\\bin``, so every
JDK 11+ user hit "WindowsAccessBridge dll not found" unless they passed an
explicit path or set ``JAB_HOME``.  :func:`find_bridge_dll` replaces that
single-path lookup with an ordered search that also covers vendor install
locations and a bounded recursive fallback.

The search helpers are deliberately free of any Windows-only import, so the
logic can be unit tested on any platform.
"""

import os
import struct
from pathlib import Path
from typing import Iterator, List, Optional

MAX_STRING_SIZE = 1024
SHORT_STRING_SIZE = 256
MAX_KEY_BINDINGS = 50
MAX_RELATION_TARGETS = 25
MAX_RELATIONS = 5
MAX_ACTION_INFO = 256
MAX_ACTIONS_TO_DO = 32
MAX_VISIBLE_CHILDREN = 256

#: How deep a lookup will walk before giving up.
#:
#: The accessibility tree is not guaranteed to be a tree.  Java Access Bridge will
#: report a parent among a node's descendants if the application's accessibility
#: implementation is wrong or mid-update, and a recursive walk with no ceiling
#: follows that forever -- which is a hang, not an exception, because every step is
#: a fresh cross-process call that succeeds.  A real Swing hierarchy is well under
#: twenty deep (``AccessibleContextInfo.objectDepth`` says how deep), so a hundred
#: is far past anything legitimate and still bounded.
MAX_SEARCH_DEPTH = 100
TIMEOUT = 30

#: Seconds to sleep between attempts while waiting for a Java window to appear.
#: The message queue is pumped once per iteration, so this also bounds how
#: often COM accessibility events get serviced while waiting.
WINDOW_POLL_INTERVAL = 0.05

#: Seconds to sleep between attempts while waiting for an element to appear.
#: Element lookups walk the accessibility tree, so polling hard in a loop burns
#: CPU for no benefit; see issues #29 and #33.
ELEMENT_POLL_INTERVAL = 0.1

# set JAB dll
WAB_DLL = "WindowsAccessBridge-{}.dll"

# ---------------------------------------------------------------------------
# Legacy constants, kept for backwards compatibility.
#
# .. deprecated::
#    DLL discovery is now performed by :func:`find_bridge_dll`.  These
#    constants only describe the historical single-path lookups and no longer
#    reflect where JAB actually lives on modern JDKs.  Prefer the functions
#    below.
# ---------------------------------------------------------------------------
JDK_BRIDGE_DLL = os.environ.get("JAVA_HOME", ".") + f"\\jre\\bin\\{WAB_DLL}"
JRE_BRIDGE_DLL = os.environ.get("JRE_HOME", ".") + f"\\bin\\{WAB_DLL}"
JAB_BRIDGE_DLL = os.environ.get("JAB_HOME", ".") + f"\\{WAB_DLL}"

#: Environment variables that may point at a JDK, a JRE or a standalone JAB.
_HOME_ENV_VARS = ("JAVA_HOME", "JDK_HOME", "JRE_HOME", "JAB_HOME")

#: Maximum directory depth used by the recursive fallback search.
_MAX_SEARCH_DEPTH = 4

#: Roots that commonly contain a JDK on Windows, scanned at most one level deep.
_PROGRAM_ROOTS = (
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.expanduser(r"~\.jdks"),                  # IntelliJ downloaded JDKs
    os.path.expanduser(r"~\scoop\apps"),
    os.path.expanduser(r"~\AppData\Local\Programs"),
)

#: Where the JDK looks for the switch that turns Java Access Bridge on.  A
#: per-user file, so it decides the answer for every Java program this account
#: starts, not only for pyjab.
A11Y_PROPS_PATH = os.path.expanduser(r"~\.accessibility.properties")

#: What that file has to contain for the bridge to attach.  Both lines are read
#: by the JDK: the first names the assistive technology to load, the second is
#: the companion setting documented alongside it.  Neither value is pyjab's to
#: choose -- they are the interface, and the JDK is what gives them meaning.
A11Y_PROPS_CONTENT = (
    "assistive_technologies=com.sun.java.accessibility.AccessBridge\n"
    "screen_magnifier_present=true\n"
)


def get_dll_bit() -> int:
    """Return the bitness (32 or 64) of the running Python interpreter.

    The JAB bridge DLL is loaded *into this process*, so the file that must be
    found is the one matching the interpreter's bitness -- not necessarily the
    JVM's.
    """
    return struct.calcsize("P") * 8


def _as_dir(value: Optional[str]) -> Optional[Path]:
    """Interpret an environment variable value as an existing directory."""
    if not value:
        return None
    # Environment values are frequently quoted, and may carry a trailing slash.
    candidate = Path(value.strip().strip('"').strip("'"))
    return candidate if candidate.is_dir() else None


def _iter_subdirs(root: Path) -> Iterator[Path]:
    """Yield the immediate subdirectories of *root*, tolerating permission errors."""
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_dir():
                yield entry
        except OSError:
            continue


def get_bridge_dll_search_dirs() -> List[Path]:
    """Return every directory that may hold the JAB bridge DLL.

    Directories are ordered by likelihood and de-duplicated case-insensitively
    (Windows paths are case-insensitive).
    """
    dirs: List[Path] = []
    seen = set()

    def add(path: Optional[Path]) -> None:
        if path is None:
            return
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        dirs.append(path)

    # 1. Locations derived from environment variables, JDK 11+ before JDK <= 10.
    for var in _HOME_ENV_VARS:
        home = _as_dir(os.environ.get(var))
        if home is None:
            continue
        add(home / "bin")
        add(home / "jre" / "bin")
        add(home)

    # 2. Vendor install locations, identified by a java executable or a jdk-ish name.
    for root in _PROGRAM_ROOTS:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        add(root_path / "bin")
        add(root_path / "jre" / "bin")
        for child in _iter_subdirs(root_path):
            has_jdk_layout = (child / "bin" / "java.exe").is_file()
            has_jre_layout = (child / "jre" / "bin" / "java.exe").is_file()
            if has_jdk_layout or has_jre_layout or "jdk" in child.name.lower():
                add(child / "bin")
                add(child / "jre" / "bin")

    return dirs


def get_bridge_dll_candidates(dll_bit: Optional[int] = None) -> List[Path]:
    """Return candidate DLL paths, most likely first.

    Args:
        dll_bit: ``32`` or ``64``.  Defaults to the running interpreter's bitness.
    """
    bit = dll_bit or get_dll_bit()
    filename = WAB_DLL.format(bit)
    return [directory / filename for directory in get_bridge_dll_search_dirs()]


def _recursive_candidates(dll_bit: int) -> Iterator[Path]:
    """Search the JDK/JRE homes recursively, bounded by ``_MAX_SEARCH_DEPTH``."""
    filename = WAB_DLL.format(dll_bit)
    for var in _HOME_ENV_VARS:
        home = _as_dir(os.environ.get(var))
        if home is None:
            continue
        base_depth = len(home.parts)
        try:
            for found in home.rglob(filename):
                if len(found.parts) - base_depth <= _MAX_SEARCH_DEPTH:
                    yield found
        except OSError:
            continue


def find_bridge_dll(dll_bit: Optional[int] = None) -> Optional[Path]:
    """Locate the JAB bridge DLL.

    Args:
        dll_bit: ``32`` or ``64``.  Defaults to the running interpreter's bitness.

    Returns:
        The path to an existing DLL, or ``None`` when nothing was found.
    """
    for candidate in get_bridge_dll_candidates(dll_bit):
        if candidate.is_file():
            return candidate
    for found in _recursive_candidates(dll_bit or get_dll_bit()):
        if found.is_file():
            return found
    return None


def describe_bridge_dll_search(dll_bit: Optional[int] = None) -> str:
    """Build an actionable diagnostic message for a failed DLL search.

    The message reports which environment variables were consulted, which
    directories were probed and -- most usefully -- whether a DLL of the
    *wrong bitness* was found, which is a common and otherwise very confusing
    failure mode.
    """
    bit = dll_bit or get_dll_bit()
    other_bit = 32 if bit == 64 else 64
    filename = WAB_DLL.format(bit)

    lines = [
        f"Java Access Bridge DLL ({filename}) could not be located.",
        "",
        "Environment variables:",
    ]
    for var in _HOME_ENV_VARS:
        value = os.environ.get(var)
        suffix = "" if value else "  (not set)"
        lines.append(f"  {var} = {value!r}{suffix}")

    lines.append("")
    lines.append(f"Directories probed for {filename}:")
    search_dirs = get_bridge_dll_search_dirs()
    if not search_dirs:
        lines.append(
            "  (none -- none of JAVA_HOME/JDK_HOME/JRE_HOME/JAB_HOME is set, and "
            "no known install location exists)"
        )
    for directory in search_dirs[:20]:
        lines.append(f"  {directory}")
    if len(search_dirs) > 20:
        lines.append(f"  ... and {len(search_dirs) - 20} more")

    wrong_bit_hit = find_bridge_dll(other_bit)
    if wrong_bit_hit is not None:
        lines += [
            "",
            f"NOTE: found a {other_bit}-bit DLL instead:",
            f"  {wrong_bit_hit}",
            f"This interpreter is {bit}-bit, so that file cannot be loaded. "
            f"Install a {bit}-bit JDK, or run Python in {other_bit}-bit mode.",
        ]

    lines += [
        "",
        "How to fix:",
        "  1. Install a JDK and set JAVA_HOME to its installation directory.",
        "  2. Or set JAB_HOME to the directory holding the DLL.",
        f'  3. Or pass the path explicitly: JABDriver(bridge_dll=r"<path>\\{filename}")',
        "",
        "To locate the file manually, run in PowerShell:",
        '  Get-ChildItem -Path "C:\\Program Files" -Recurse '
        f'-Filter "{filename}" -ErrorAction SilentlyContinue',
    ]
    return "\n".join(lines)
