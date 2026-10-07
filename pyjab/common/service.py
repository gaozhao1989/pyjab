from ctypes import cdll
from ctypes import CDLL
from pathlib import Path
from typing import Optional

from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton
from pyjab.config import A11Y_PROPS_CONTENT
from pyjab.config import A11Y_PROPS_PATH
from pyjab.config import describe_bridge_dll_search
from pyjab.config import find_bridge_dll


@singleton
class Service(object):
    def __init__(self) -> None:
        self.logger = Logger("pyjab")
        self.init_bridge()

    def enable_bridge(self) -> None:
        """Write the file that makes the JDK load Java Access Bridge.

        The whole operation is guarded, not only the write inside it.  Opening
        the file is the step that actually fails -- a roaming or locked-down home
        directory is the usual reason -- and an unguarded ``open`` there means
        the error handler below it can never run and ``JABDriver()`` raises from
        its constructor instead.
        """
        try:
            with open(A11Y_PROPS_PATH, "wt") as fp:
                fp.write(A11Y_PROPS_CONTENT)
        except OSError as exc:
            self.logger.error("could not enable Java Access Bridge: %s", exc)
        else:
            self.logger.debug("Java Access Bridge enabled in %s", A11Y_PROPS_PATH)

    def is_bridge_enabled(self) -> bool:
        """Whether the properties file already says exactly what we would write.

        Compared in full rather than by looking for the class name inside it.  A
        file that merely mentions ``AccessBridge`` may also configure other
        assistive technologies, and rewriting it would silently take those away.

        Anything that prevents reading the file counts as "not enabled", so that
        the attempt to write it is what reports the problem.
        """
        try:
            with open(A11Y_PROPS_PATH, "rt") as fp:
                current = fp.read()
        except FileNotFoundError:
            return False
        except OSError as exc:
            self.logger.error("could not read %s: %s", A11Y_PROPS_PATH, exc)
            return False

        enabled = current == A11Y_PROPS_CONTENT
        self.logger.debug("Java Access Bridge already enabled: %s", enabled)
        return enabled

    def init_bridge(self) -> None:
        self.logger.debug("init bridge")
        if not self.is_bridge_enabled():
            self.enable_bridge()

    def find_bridge_dll(self, bridge_dll: Optional[str] = None) -> Optional[Path]:
        """Locate the Java Access Bridge DLL without loading it.

        Useful for diagnostics: it reports *where* the DLL would be loaded from
        without actually loading it into the process.

        Args:
            bridge_dll: An explicit DLL path supplied by the caller.  When given
                and valid it takes precedence over all automatic discovery.

        Returns:
            The path to the DLL, or ``None`` when it could not be located.
        """
        if bridge_dll:
            explicit = Path(str(bridge_dll))
            if explicit.is_file():
                return explicit
            self.logger.warning(
                "The explicit bridge_dll path does not exist: '{}'. "
                "Falling back to automatic discovery.".format(bridge_dll)
            )
        return find_bridge_dll()

    def load_library(self, bridge_dll: str = "") -> CDLL:
        """Load the Java Access Bridge DLL.

        Resolution order:

        1. The ``bridge_dll`` argument, when it points at an existing file.
        2. :func:`pyjab.config.find_bridge_dll`, which probes
           ``%JAVA_HOME%\\bin`` (JDK 11+), ``%JAVA_HOME%\\jre\\bin`` (JDK 8-10),
           ``%JRE_HOME%``, ``%JAB_HOME%``, common vendor install locations and
           finally performs a bounded recursive search.

        Args:
            bridge_dll: Explicit path to ``WindowsAccessBridge-XX.dll``.
                Defaults to "" (automatic discovery).

        Raises:
            FileNotFoundError: When no DLL could be located.  The message lists
                every location that was probed and how to fix the situation.
        """
        self.logger.debug("load library of bridge")

        resolved = self.find_bridge_dll(bridge_dll)
        if resolved is None:
            raise FileNotFoundError(describe_bridge_dll_search())

        self.logger.debug("Loading Java Access Bridge DLL from '{}'".format(resolved))
        return cdll.LoadLibrary(str(resolved))
