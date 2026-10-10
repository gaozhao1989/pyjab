"""The JVM-path-to-directories rule, which is pure and therefore testable here.

This is the portable half of deriving the bridge DLL's location from a running JVM.
The Windows half -- asking processes for their image paths -- needs Windows; this does not,
and it holds the part that is easy to get wrong.

It was wrong on first writing, in a way only this file could have caught:
``Path(r"C:\\a\\java.exe").name`` is the whole string on POSIX, because a backslash is not
a separator there. The function returned nothing, on the two platforms where the suite runs
for every commit, about paths that only occur on the third.
"""

from __future__ import annotations

import pytest

from pyjab.config import bridge_dirs_from_image


def test_a_private_jre_is_found_from_the_jvm_that_is_running():
    """The case the whole thing exists for.

    An application bundled with its own JRE, in a directory nothing would guess. The
    application is running, so its JVM can be asked -- and that JVM's own DLL is also the
    correct one to use, because the client DLL pairs with the bridge inside the target.
    """
    dirs = bridge_dirs_from_image(r"C:\Apps\Vendor\jre\bin\java.exe")

    assert [str(d) for d in dirs][0] == r"C:\Apps\Vendor\jre\bin"


def test_a_jdk_8_layout_offers_the_bundled_jre_bin_too():
    """JDK 8-10 keep the bridge in ``jre\\bin``, JDK 11+ in ``bin``."""
    dirs = bridge_dirs_from_image(r"C:\Programs\jdk-8\bin\java.exe")

    assert [str(d) for d in dirs] == [
        r"C:\Programs\jdk-8\bin",
        r"C:\Programs\jdk-8\jre\bin",
    ]


def test_javaw_counts_as_a_jvm():
    """A Swing application launched without a console runs as javaw.exe."""
    assert bridge_dirs_from_image(r"C:\Programs\jdk-21\bin\javaw.exe")


@pytest.mark.parametrize("image", [
    r"C:\Windows\System32\notepad.exe",
    r"C:\Program Files\App\bin\launcher.exe",
    "",
    "java.exe",
])
def test_something_that_is_not_a_jvm_yields_nothing(image):
    """Better to find nothing than to point the search at a random directory."""
    assert bridge_dirs_from_image(image) == []


def test_the_result_is_real_path_objects():
    """The callers do `directory / name` and then `.is_file()`.

    A ``PureWindowsPath`` has no filesystem methods, so returning one would fail at the
    next step rather than here.
    """
    for directory in bridge_dirs_from_image(r"C:\Apps\jre\bin\java.exe"):
        assert isinstance(directory, type(__import__("pathlib").Path()))
        assert callable(directory.is_file)
