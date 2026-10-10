"""The running-JVM search folds into the DLL discovery without being able to break it.

This is the half of the feature that is testable anywhere: the Windows call that produces
JVM image paths lives in ``win32utils`` and needs a Windows machine, but what ``Service``
does with the answer is platform independent and is where the risk is.

A note on the patch target: ``Win32Utils`` is decorated with ``@singleton``, which replaces
the class with a wrapper *function* (AGENTS.md 2.2). Patching ``Win32Utils.method`` therefore
patches an attribute on the wrapper and does nothing at all -- the real method runs, and the
test passes or fails for reasons unrelated to what it claims to check. The target is
``Win32Utils.__wrapped__``.

The risk is specific. This search only *adds* candidates to a search that already works, so
a failure in it must leave the original search intact. The tempting shape -- let the
exception propagate, or return an empty list that replaces the real one -- turns a nicety
into a regression for everyone whose DLL was being found fine.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import _win32stubs  # noqa: F401

from pyjab.common.service import Service


def a_service():
    """A Service with the bridge init stubbed, so no home directory is touched.

    ``Service()`` writes ``~/.accessibility.properties`` when the bridge is not already
    enabled -- fine in production, unacceptable in a test.
    """
    with patch.object(Service.__wrapped__, "init_bridge", lambda self: None):
        service = Service()
    return service


def test_a_jvm_that_cannot_be_asked_leaves_the_search_intact():
    """The failure mode to avoid: a nicety that breaks what worked."""
    service = a_service()

    with patch("pyjab.common.win32utils.Win32Utils.__wrapped__.java_process_image_paths",
               side_effect=OSError("no")):
        assert service._dirs_from_running_jvms() == []


def test_no_running_jvm_is_an_empty_answer_not_an_error():
    service = a_service()

    with patch("pyjab.common.win32utils.Win32Utils.__wrapped__.java_process_image_paths",
               return_value=[]):
        assert service._dirs_from_running_jvms() == []


def test_the_directories_come_from_the_jvms_that_answered():
    service = a_service()
    images = [r"C:\Apps\Vendor\jre\bin\java.exe", r"C:\Programs\jdk-21\bin\javaw.exe"]

    with patch("pyjab.common.win32utils.Win32Utils.__wrapped__.java_process_image_paths",
               return_value=images):
        dirs = service._dirs_from_running_jvms()

    assert Path(r"C:\Apps\Vendor\jre\bin") in dirs
    assert Path(r"C:\Programs\jdk-21\bin") in dirs


def test_duplicates_are_removed():
    """Two windows of one application share a JVM and must not add it twice."""
    service = a_service()
    image = r"C:\Apps\Vendor\jre\bin\java.exe"

    with patch("pyjab.common.win32utils.Win32Utils.__wrapped__.java_process_image_paths",
               return_value=[image, image]):
        dirs = service._dirs_from_running_jvms()

    assert len(dirs) == len(set(dirs))


def test_the_extra_directories_are_offered_to_the_search():
    """Wired in, not merely computed."""
    service = a_service()

    with patch("pyjab.common.win32utils.Win32Utils.__wrapped__.java_process_image_paths",
               return_value=[r"C:\Apps\Vendor\jre\bin\java.exe"]), \
         patch("pyjab.common.service.find_bridge_dll", return_value=None) as finder:
        service.find_bridge_dll()

    assert finder.called
    extra = finder.call_args.kwargs.get("extra_dirs")
    assert extra, "the JVM-derived directories were not passed to the search"
