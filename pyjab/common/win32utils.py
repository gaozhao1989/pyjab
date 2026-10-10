import ctypes
import fnmatch
import time
from ctypes.wintypes import DWORD, HWND
from typing import Dict, List, Optional
import pythoncom
import win32api
import win32clipboard
import win32com.client
import win32con
import win32gui
import win32process
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton
from pyjab.config import TIMEOUT


def double_click_gap() -> float:
    """Half the system double-click interval, in seconds.

    Half of it is safely inside the window whether the setting is 200ms or 900ms,
    which is why the division is by 2000 rather than 1000.

    Through ``ctypes`` and ``user32`` rather than ``win32api``.  ``GetDoubleClickTime``
    is a ``user32`` export and is always there; **``win32api`` does not expose it at
    all** on a current pywin32.  That is how this was found: the GUI suite failed on
    Windows with ``AttributeError: module 'win32api' has no attribute
    'GetDoubleClickTime'`` while CI stayed green, because CI never runs the GUI
    suite.

    Module level rather than a staticmethod so that it can be called without going
    through the ``@singleton`` wrapper -- ``functools.wraps`` copies the class
    dictionary onto that wrapper, and a ``staticmethod`` object is not callable
    there on Python 3.9.
    """
    return ctypes.windll.user32.GetDoubleClickTime() / 2000.0


#: PROCESS_DPI_AWARENESS values that mean "this process does its own scaling".
PROCESS_DPI_SYSTEM_AWARE = 2
PROCESS_DPI_PER_MONITOR_AWARE = 3
PROCESS_DPI_PER_MONITOR_AWARE_V2 = 4
_AWARE_VALUES = (
    PROCESS_DPI_SYSTEM_AWARE,
    PROCESS_DPI_PER_MONITOR_AWARE,
    PROCESS_DPI_PER_MONITOR_AWARE_V2,
)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


def _declare(*functions) -> None:
    """Set the ctypes signature of a shcore entry point.

    Without ``argtypes`` ctypes masks integer arguments to C ``int``, so a 64-bit
    handle passed as a Python ``int`` silently becomes 32 bits; without ``restype``
    a returned handle is truncated the same way.  AGENTS.md 2.8 is about exactly
    this, and "it happens to work for these particular values" is how the next one
    gets written.
    """
    for function, argtypes in functions:
        function.argtypes = argtypes
        function.restype = ctypes.c_long


def display_scale(hwnd: int) -> float:
    """The scale factor of the display *hwnd* is on, as a float, 1.0 if unknown.

    Read through a thread that is temporarily made DPI aware.  Both
    ``GetDpiForWindow`` and ``GetDpiForMonitor`` answer **96 for an unaware
    caller** -- Microsoft documents a flat 96 on the Unaware row of each -- so from
    a process that declares no awareness, which is what pyjab is, neither one can
    see a 150% display at all.  ``SetThreadDpiAwarenessContext`` changes the calling
    thread only and is undone in a ``finally``.
    """
    try:
        user32 = ctypes.windll.user32
        shcore = ctypes.windll.shcore
        monitor = user32.MonitorFromWindow(HWND(hwnd), MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return 1.0

        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        previous = user32.GetThreadDpiAwarenessContext()
        user32.SetThreadDpiAwarenessContext(
            ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
        try:
            dpi_x, dpi_y = ctypes.c_uint(), ctypes.c_uint()
            hresult = shcore.GetDpiForMonitor(
                ctypes.c_void_p(monitor), MDT_EFFECTIVE_DPI,
                ctypes.byref(dpi_x), ctypes.byref(dpi_y),
            )
            if hresult != 0 or not dpi_x.value:
                return 1.0
            return dpi_x.value / 96.0
        finally:
            user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))
    except Exception:  # pragma: no cover - Windows 8 and older, or no shcore
        return 1.0


def target_dpi_aware(hwnd: int) -> Optional[bool]:
    """Whether the process owning *hwnd* does its own DPI scaling, or None.

    None means it could not be determined, which is different from False: an
    elevated target cannot be opened, and guessing "unaware" there would move the
    cursor on a setup that works.
    """
    k32 = ctypes.windll.kernel32
    shcore = ctypes.windll.shcore
    handle = None
    try:
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(HWND(hwnd), ctypes.byref(pid))
        if not pid.value:
            return None
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        awareness = ctypes.c_int()
        hresult = shcore.GetProcessDpiAwareness(
            ctypes.c_void_p(handle), ctypes.byref(awareness)
        )
        if hresult != 0:
            return None
        return awareness.value in _AWARE_VALUES
    except Exception:  # pragma: no cover - platform dependent
        return None
    finally:
        if handle:
            try:
                k32.CloseHandle(ctypes.c_void_p(handle))
            except Exception:  # pragma: no cover
                pass


def thread_dpi_aware() -> Optional[bool]:
    """Whether the calling thread's coordinates are taken as physical.

    This is the half that decides how ``SetCursorPos`` reads its arguments, and
    which Tk (so Tkinter), and anything else that calls
    ``SetProcessDpiAwareness``, can turn on inside a process that never asked.
    """
    try:
        user32 = ctypes.windll.user32
        user32.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.GetAwarenessFromDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        context = user32.GetThreadDpiAwarenessContext()
        awareness = user32.GetAwarenessFromDpiAwarenessContext(
            ctypes.c_void_p(context)
        )
        return awareness in _AWARE_VALUES
    except Exception:  # pragma: no cover - Windows 10 1607 and older
        return None


def physical_point(x: int, y: int, hwnd: int) -> tuple:
    """Convert a point reported by JAB into the point the mouse API wants.

    Issue #62. The coordinates JAB returns are the **target's**, and the mouse
    coordinates ``SetCursorPos`` takes are the **calling thread's**. When the two
    processes scale differently those are different spaces, and pyjab moves the
    cursor to the wrong place with nothing reporting an error.

    Measured, at 150% scaling, with a target that is unaware:

    ===================  ==========================================
    calling thread       clicking the JAB point
    ===================  ==========================================
    unaware (pyjab)      **lands** -- both spaces are logical
    aware                **misses**; the point x1.5 lands
    ===================  ==========================================

    So the rule is to convert only when the two differ, and in the direction that
    is missing: an aware caller needs the target's logical point scaled **up** into
    physical space, an unaware caller needs a physical point scaled **down** so
    that Windows' own virtualisation scales it back.

    When either side cannot be determined, or the display is at 100%, the point is
    returned unchanged. That is the behaviour pyjab has always had, and it is the
    one that works for the default configuration -- an unaware process against an
    unaware target -- which is every setup nobody has complained about.
    """
    scale = display_scale(hwnd)
    if scale == 1.0:
        return int(x), int(y)

    aware_caller = thread_dpi_aware()
    aware_target = target_dpi_aware(hwnd)
    if aware_caller is None or aware_target is None:
        return int(x), int(y)

    if aware_caller and not aware_target:
        return round(x * scale), round(y * scale)
    if aware_target and not aware_caller:
        return round(x / scale), round(y / scale)
    return int(x), int(y)


@singleton
class Win32Utils(object):
    virtual_key_code = {
        "backspace": 0x08,
        "tab": 0x09,
        "clear": 0x0C,
        "enter": 0x0D,
        "shift": 0x10,
        "ctrl": 0x11,
        "alt": 0x12,
        "pause": 0x13,
        "caps_lock": 0x14,
        "esc": 0x1B,
        "spacebar": 0x20,
        "page_up": 0x21,
        "page_down": 0x22,
        "end": 0x23,
        "home": 0x24,
        "left_arrow": 0x25,
        "up_arrow": 0x26,
        "right_arrow": 0x27,
        "down_arrow": 0x28,
        "select": 0x29,
        "print": 0x2A,
        "execute": 0x2B,
        "print_screen": 0x2C,
        "ins": 0x2D,
        "del": 0x2E,
        "help": 0x2F,
        "0": 0x30,
        "1": 0x31,
        "2": 0x32,
        "3": 0x33,
        "4": 0x34,
        "5": 0x35,
        "6": 0x36,
        "7": 0x37,
        "8": 0x38,
        "9": 0x39,
        "a": 0x41,
        "b": 0x42,
        "c": 0x43,
        "d": 0x44,
        "e": 0x45,
        "f": 0x46,
        "g": 0x47,
        "h": 0x48,
        "i": 0x49,
        "j": 0x4A,
        "k": 0x4B,
        "l": 0x4C,
        "m": 0x4D,
        "n": 0x4E,
        "o": 0x4F,
        "p": 0x50,
        "q": 0x51,
        "r": 0x52,
        "s": 0x53,
        "t": 0x54,
        "u": 0x55,
        "v": 0x56,
        "w": 0x57,
        "x": 0x58,
        "y": 0x59,
        "z": 0x5A,
        "numpad_0": 0x60,
        "numpad_1": 0x61,
        "numpad_2": 0x62,
        "numpad_3": 0x63,
        "numpad_4": 0x64,
        "numpad_5": 0x65,
        "numpad_6": 0x66,
        "numpad_7": 0x67,
        "numpad_8": 0x68,
        "numpad_9": 0x69,
        "multiply_key": 0x6A,
        "add_key": 0x6B,
        "separator_key": 0x6C,
        "subtract_key": 0x6D,
        "decimal_key": 0x6E,
        "divide_key": 0x6F,
        "F1": 0x70,
        "F2": 0x71,
        "F3": 0x72,
        "F4": 0x73,
        "F5": 0x74,
        "F6": 0x75,
        "F7": 0x76,
        "F8": 0x77,
        "F9": 0x78,
        "F10": 0x79,
        "F11": 0x7A,
        "F12": 0x7B,
        "F13": 0x7C,
        "F14": 0x7D,
        "F15": 0x7E,
        "F16": 0x7F,
        "F17": 0x80,
        "F18": 0x81,
        "F19": 0x82,
        "F20": 0x83,
        "F21": 0x84,
        "F22": 0x85,
        "F23": 0x86,
        "F24": 0x87,
        "num_lock": 0x90,
        "scroll_lock": 0x91,
        "left_shift": 0xA0,
        # Was "right_shift " with a trailing space, so looking up the key by its
        # actual name raised KeyError.
        "right_shift": 0xA1,
        "left_control": 0xA2,
        "right_control": 0xA3,
        "left_menu": 0xA4,
        "right_menu": 0xA5,
        "browser_back": 0xA6,
        "browser_forward": 0xA7,
        "browser_refresh": 0xA8,
        "browser_stop": 0xA9,
        "browser_search": 0xAA,
        "browser_favorites": 0xAB,
        "browser_start_and_home": 0xAC,
        "volume_mute": 0xAD,
        "volume_Down": 0xAE,
        "volume_up": 0xAF,
        "next_track": 0xB0,
        "previous_track": 0xB1,
        "stop_media": 0xB2,
        "play/pause_media": 0xB3,
        "start_mail": 0xB4,
        "select_media": 0xB5,
        "start_application_1": 0xB6,
        "start_application_2": 0xB7,
        "attn_key": 0xF6,
        "crsel_key": 0xF7,
        "exsel_key": 0xF8,
        "play_key": 0xFA,
        "zoom_key": 0xFB,
        "clear_key": 0xFE,
        # VK_OEM_PLUS is the '='/ '+' key: '=' is the unshifted character, '+'
        # is shift plus it. Only '+' was in this table, so _send_keys()'s own
        # entry for '+' -- which expands to ('left_shift', '=') -- raised
        # KeyError, and typing a plus sign failed.
        "=": 0xBB,
        "+": 0xBB,
        ",": 0xBC,
        "-": 0xBD,
        ".": 0xBE,
        "/": 0xBF,
        "`": 0xC0,
        ";": 0xBA,
        "[": 0xDB,
        "\\": 0xDC,
        "]": 0xDD,
        "'": 0xDE,
    }

    def __init__(self) -> None:
        self.logger = Logger("pyjab")

    def pump_messages(self) -> bool:
        """Service every Windows/COM message currently queued for this thread.

        The Java Access Bridge is COM based, and COM callbacks -- including the
        accessibility events that announce newly opened windows and dialogs --
        are delivered to the thread that called ``Windows_run()``.  That thread
        must therefore service its message queue, or those events never arrive
        and pyjab cannot see a window that opens later.

        This is deliberately a plain, non-blocking call rather than the
        generator driven by :class:`~pyjab.common.actorscheduler.ActorScheduler`
        that it replaces:

        * the old pump only ran while pyjab was waiting for the *first* window,
          so nothing was serviced once element lookups started;
        * it blocked for up to 200ms per invocation, even when idle;
        * every call built a fresh generator that was discarded immediately, so
          no pump state survived between calls, and each discarded generator
          signalled the shared stop event -- which made every second call a
          no-op.

        Call it as often as convenient; with an empty queue it is very cheap.

        Returns:
            bool: True if a WM_QUIT was seen, otherwise False.
        """
        try:
            return bool(pythoncom.PumpWaitingMessages())
        except pythoncom.com_error:
            # No COM message queue on this thread -- COM was never initialised
            # here, which happens when the caller is not the thread that ran
            # Windows_run().  Nothing to service; not an error.
            self.logger.debug("no COM message queue on this thread, nothing to pump")
            return False

    #: Process access right needed to ask a process for its image path. The *limited*
    #: information right rather than PROCESS_QUERY_INFORMATION, because it is the one that
    #: works on a process owned by another user and does not ask for anything more than
    #: this needs.
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    @staticmethod
    def java_process_image_paths() -> List[str]:
        """Image paths of running JVMs, taken from the windows they own.

        **Why this can run before the bridge DLL is loaded.** Enumerating windows is plain
        Win32 and needs nothing from Java; `isJavaWindow`, by contrast, is a bridge call and
        therefore needs the DLL. Since the DLL search happens *before* a window can be asked
        anything, looking at windows is the only way to learn where a running JVM's own DLL
        is -- which is the case that matters, an application bundled with a private JRE that
        no install-location search would guess.

        Using the target JVM's own DLL is also the correct one to use: the client DLL pairs
        with the bridge inside the JVM, and a mismatched pair fails as "pyjab cannot see my
        window" -- the hardest failure in this project to tell apart from the bridge simply
        not being enabled.

        Returns:
            list: Image paths, de-duplicated, in enumeration order. Empty when nothing
            looks like a JVM, which is a normal answer rather than an error.
        """
        found: List[str] = []
        seen = set()

        def visit(hwnd, _):
            try:
                _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
                if not pid or pid in seen:
                    return
                seen.add(pid)
                path = Win32Utils._process_image_path(pid)
            except Exception:
                # A window that dies mid-enumeration, or a process that refuses to be
                # asked. Neither is a reason to abandon the ones that answer.
                return
            if not path:
                return
            if path.lower().endswith(("\\java.exe", "\\javaw.exe")):
                if path not in found:
                    found.append(path)

        win32gui.EnumWindows(visit, 0)
        return found

    @staticmethod
    def _process_image_path(pid: int) -> Optional[str]:
        """The full image path of *pid*, or None if it cannot be read.

        ctypes rather than ``win32process.GetModuleFileNameEx``: the latter wants
        ``PROCESS_VM_READ``, which is a larger right than this needs and is refused in more
        situations.
        """
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            Win32Utils._PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return None
        try:
            size = DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)
            ):
                return None
            return buffer.value or None
        finally:
            kernel32.CloseHandle(handle)

    #: BitBlt's "copy the pixels" raster operation.
    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0

    def grab_rect(self, x: int, y: int, width: int, height: int) -> bytes:
        """The pixels of a screen rectangle, as a top-down BGRA buffer.

        Pure ctypes over GDI: ``BitBlt`` from the screen into a memory device context, then
        ``GetDIBits`` for the bits. This is what replaces ``PIL.ImageGrab``, which was the
        only reason Pillow was a dependency.

        **Why not simply return an image.** :mod:`pyjab.common.png` turns this buffer into
        a file with nothing but ``zlib``, and keeping the two apart means the encoder -- the
        part that is easy to get subtly wrong -- is testable on any platform, with synthetic
        pixels, while this part needs a screen.

        Args:
            x: Left edge, in **physical** screen coordinates. See
                :func:`pyjab.common.win32utils.physical_point` for why that matters.
            y: Top edge, physical screen coordinates.
            width: Pixels across.
            height: Pixels down.

        Returns:
            bytes: ``width * height * 4`` bytes, B, G, R, A per pixel, **top row first**.
            ``GetDIBits`` produces bottom-up for a positive height, so the header's height
            is negated here to ask for top-down -- easier than reversing rows and less easy
            to forget.

        Raises:
            RuntimeError: a GDI call failed, with which one. Silent failure here would
                produce a black image, which is indistinguishable from a black window.
        """
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        screen_dc = user32.GetDC(None)
        if not screen_dc:
            raise RuntimeError("GetDC(NULL) failed, so there is no screen to read")
        memory_dc = None
        bitmap = None
        previous = None
        try:
            memory_dc = gdi32.CreateCompatibleDC(screen_dc)
            if not memory_dc:
                raise RuntimeError("CreateCompatibleDC failed")
            bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
            if not bitmap:
                raise RuntimeError(f"CreateCompatibleBitmap failed for {width}x{height}")
            previous = gdi32.SelectObject(memory_dc, bitmap)
            if not gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, x, y, self.SRCCOPY):
                raise RuntimeError(
                    f"BitBlt failed for the rectangle {x},{y},{width},{height}"
                )

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", ctypes.wintypes.DWORD),
                    ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long),
                    ("biPlanes", ctypes.wintypes.WORD),
                    ("biBitCount", ctypes.wintypes.WORD),
                    ("biCompression", ctypes.wintypes.DWORD),
                    ("biSizeImage", ctypes.wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", ctypes.wintypes.DWORD),
                    ("biClrImportant", ctypes.wintypes.DWORD),
                ]

            header = BITMAPINFOHEADER()
            header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            header.biWidth = width
            header.biHeight = -height          # negative: top-down, see the docstring
            header.biPlanes = 1
            header.biBitCount = 32
            header.biCompression = 0           # BI_RGB

            buffer = ctypes.create_string_buffer(width * height * 4)
            scanned = gdi32.GetDIBits(
                memory_dc, bitmap, 0, height, buffer,
                ctypes.byref(header), self.DIB_RGB_COLORS,
            )
            if scanned != height:
                raise RuntimeError(
                    f"GetDIBits returned {scanned} of {height} rows; the image would be "
                    "partly uninitialised"
                )
            return buffer.raw
        finally:
            if previous and memory_dc:
                gdi32.SelectObject(memory_dc, previous)
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if memory_dc:
                gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)

    @staticmethod
    def enum_windows() -> Dict[HWND, str]:
        dict_hwnd = dict()

        def get_all_hwnds(hwnd, _):
            if (
                win32gui.IsWindow(hwnd)
                and win32gui.IsWindowEnabled(hwnd)
                and win32gui.IsWindowVisible(hwnd)
            ):
                dict_hwnd.update({hwnd: win32gui.GetWindowText(hwnd)})

        win32gui.EnumWindows(get_all_hwnds, 0)
        return dict_hwnd

    def get_hwnd_by_title(self, title: str) -> Optional[HWND]:
        if possible_matches := self.get_hwnds_by_title(title):
            return possible_matches[0]
        return None

    def get_hwnds_by_title(self, title: str) -> List[HWND]:
        dict_hwnd = self.enum_windows()
        return [hwnd for hwnd, win_title in dict_hwnd.items() if fnmatch.fnmatch(win_title, title)]

    @staticmethod
    def get_title_by_hwnd(hwnd: HWND) -> str:
        return win32api.GetWindowText(hwnd)

    def wait_hwnd_by_title(self, title: str, timeout: int = TIMEOUT) -> HWND:
        latest_log = ""
        start = time.time()
        while True:
            if hwnd := self.get_hwnd_by_title(title):
                return hwnd
            error_log = f"no hwnd found by win title =>'{title}'"
            if latest_log != error_log:
                self.logger.debug(error_log)
                latest_log = error_log
            current = time.time()
            elapsed = round(current - start)
            if elapsed >= timeout:
                raise TimeoutError(
                    f"no hwnd found by title '{title}' in '{timeout}' seconds"
                )

    @staticmethod
    def _get_foreground_window() -> HWND:
        return win32gui.GetForegroundWindow()

    def _set_window_foreground(self, hwnd: HWND) -> None:
        if hwnd == self._get_foreground_window():
            return
        win32com.client.Dispatch("WScript.Shell").SendKeys(' ')
        win32gui.SetForegroundWindow(hwnd)

    @staticmethod
    def _get_window_size(hwnd: HWND) -> tuple:
        """The bound window's size in pixels, as ``(width, height)``.

        Includes the decorations, so it is the same rectangle
        :meth:`_set_window_size` takes and :meth:`_get_window_position` reports
        the corner of.

        A tuple rather than the dict Selenium returns for the same name, to match
        :meth:`_get_window_position`, which pyjab already made a tuple.
        """
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        return (right - left, bottom - top)

    @staticmethod
    def _set_window_maximize(hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)

    @staticmethod
    def _set_window_minimize(hwnd: HWND) -> None:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

    @staticmethod
    def _set_window_size(hwnd: HWND, width: int, height: int) -> None:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(hwnd, left, top, width, height, True)

    @staticmethod
    def _set_window_position(hwnd: HWND, left: int, top: int) -> None:
        """Move the window to (left, top), keeping its current size."""
        # The current position has to be kept, not discarded: the size is the
        # distance between the *existing* edges. This previously computed
        # left - right and top - bottom from the requested position, which is
        # negative for any real window, so MoveWindow was asked for a negative
        # width and height.
        current_left, current_top, right, bottom = win32gui.GetWindowRect(hwnd)
        win32gui.MoveWindow(
            hwnd, left, top, right - current_left, bottom - current_top, True
        )

    @staticmethod
    def _get_window_position(hwnd: HWND) -> tuple:
        left, top, _, _ = win32gui.GetWindowRect(hwnd)
        return left, top

    @staticmethod
    def _click_mouse(x: int, y: int, hold: int = 0, button: str = "left") -> None:
        mouse_down_act = win32con.MOUSEEVENTF_LEFTDOWN if button == "left" else win32con.MOUSEEVENTF_RIGHTDOWN
        mouse_up_act = win32con.MOUSEEVENTF_LEFTUP if button == "left" else win32con.MOUSEEVENTF_RIGHTUP
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(mouse_down_act, x, y, 0, 0)
        if hold:
            time.sleep(hold)
        win32api.mouse_event(mouse_up_act, x, y, 0, 0)

    @staticmethod
    def _double_click_mouse(x: int, y: int) -> None:
        """Two clicks at the same place, close enough to count as one double click.

        The gap has to fall inside the system's double-click interval, which is
        configurable and therefore not a constant; see :func:`double_click_gap`.
        """
        gap = double_click_gap()
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        time.sleep(gap)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    @staticmethod
    def _get_clipboard() -> str:
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return data

    @staticmethod
    def _set_clipboard(text: str) -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        # TODO: error occurs when set clipboard
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()

    @staticmethod
    def _empty_clipboard() -> None:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()

    def _press_key(self, *keys) -> None:
        """
        one press, one release.\n
        accepts as many arguments as you want. e.g. press_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )

    def _press_and_hold_key(self, *keys) -> None:
        """
        press and hold. Do NOT release.\n
        accepts as many arguments as you want.\n
        e.g. press_and_hold_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)

    def send_keys(self, keys: str) -> None:
        """Send a keyboard shortcut, such as ``"alt+y"`` or ``"ctrl+shift+s"``.

        The public form of the chord primitive: the named keys are **held together**, then
        released in the same order. That is what makes it a shortcut rather than a sequence
        — :meth:`JABElement.send_text` types text one character at a time and types the
        letters of ``"alt+y"`` if you give it that, because text has no modifiers.

        Args:
            keys: the chord, with the keys separated by ``+``. Names are the same ones
                :attr:`virtual_key_code` uses and are case-insensitive: ``ctrl``, ``alt``,
                ``shift``, ``tab``, ``enter``, ``escape``, ``spacebar``, ``left_arrow``, a
                single letter or digit, and about a hundred more.

        Raises:
            ValueError: a name is not in the table, or the argument is empty. **Both are
                raised rather than ignored**: a shortcut that silently does nothing, or that
                sends the wrong key, is the one kind of failure here that cannot be taken
                back — it acts on somebody else's application.

        Note:
            **This sends to whatever has the keyboard focus**; it does not focus anything
            and it does not bring the window forward. A shortcut only works if the window
            meant to receive it already has focus, so a caller that has just attached to a
            window usually has to bring it forward first.

        :Usage:
            Win32Utils().send_keys("alt+y")
            Win32Utils().send_keys("ctrl+shift+s")
        """
        if not keys or not keys.strip():
            raise ValueError("send_keys() needs a key or a chord, such as 'alt+y'")

        names = [name.strip().lower() for name in keys.split("+")]
        if any(not name for name in names):
            raise ValueError(
                f"{keys!r} has an empty key name; write a chord as 'ctrl+shift+s'"
            )

        unknown = [name for name in names if name not in self.virtual_key_code]
        if unknown:
            raise ValueError(
                "unknown key name(s) {} in {!r}. Names are case-insensitive; the table has "
                "'ctrl', 'alt', 'shift', 'tab', 'enter', 'escape', 'spacebar', the arrow "
                "keys and the letters and digits.".format(", ".join(map(repr, unknown)), keys)
            )

        # One key is not a chord, but holding and releasing it is still the right thing:
        # a bare 'enter' pressed this way is what the callers of the private helper expect.
        self._press_hold_release_key(*names)

    def _press_hold_release_key(self, *keys) -> None:
        """
        press and hold passed in strings. Once held, release\n
        accepts as many arguments as you want.\n
        e.g. press_hold_release_key('left_arrow', 'a','b').\n

        this is useful for issuing shortcut command or shift commands.\n
        e.g. press_hold_release_key('ctrl', 'alt', 'del'), press_hold_release_key('shift','a')
        """
        for key in keys:
            win32api.keybd_event(self.virtual_key_code[key], 0, 0, 0)
            time.sleep(0.05)
        for key in keys:
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )
            time.sleep(0.1)

    def _release_key(self, *keys) -> None:
        """
        release depressed keys\n
        accepts as many arguments as you want.\n
        e.g. release_key('left_arrow', 'a','b').
        """
        for key in keys:
            win32api.keybd_event(
                self.virtual_key_code[key], 0, win32con.KEYEVENTF_KEYUP, 0
            )

    def _send_keys(self, text: str) -> None:
        """Simulate keyboard type for specific text.

        Characters will be typed one by one.

        None-ASCII characters will directly paste to the field(check the security option before).

        NOT RECOMMEND use this func for the text field which support auto complete.

        Args:
            text (str): text need type
        """
        if not text.isascii():
            self._paste_text(text=text)
            return
        sp_key = {
            " ": {"func": self._press_key, "keys": ["spacebar"]},
            "~": {"func": self._press_hold_release_key, "keys": ["left_shift", "`"]},
            "!": {"func": self._press_hold_release_key, "keys": ["left_shift", "1"]},
            "@": {"func": self._press_hold_release_key, "keys": ["left_shift", "2"]},
            "#": {"func": self._press_hold_release_key, "keys": ["left_shift", "3"]},
            "$": {"func": self._press_hold_release_key, "keys": ["left_shift", "4"]},
            "%": {"func": self._press_hold_release_key, "keys": ["left_shift", "5"]},
            "^": {"func": self._press_hold_release_key, "keys": ["left_shift", "6"]},
            "&": {"func": self._press_hold_release_key, "keys": ["left_shift", "7"]},
            "*": {"func": self._press_hold_release_key, "keys": ["left_shift", "8"]},
            "(": {"func": self._press_hold_release_key, "keys": ["left_shift", "9"]},
            ")": {"func": self._press_hold_release_key, "keys": ["left_shift", "0"]},
            "_": {"func": self._press_hold_release_key, "keys": ["left_shift", "-"]},
            "+": {"func": self._press_hold_release_key, "keys": ["left_shift", "="]},
            "{": {"func": self._press_hold_release_key, "keys": ["left_shift", "["]},
            "}": {"func": self._press_hold_release_key, "keys": ["left_shift", "]"]},
            "|": {"func": self._press_hold_release_key, "keys": ["left_shift", "\\"]},
            ":": {"func": self._press_hold_release_key, "keys": ["left_shift", ";"]},
            '"': {"func": self._press_hold_release_key, "keys": ["left_shift", "'"]},
            "<": {"func": self._press_hold_release_key, "keys": ["left_shift", ","]},
            ">": {"func": self._press_hold_release_key, "keys": ["left_shift", "."]},
            "?": {"func": self._press_hold_release_key, "keys": ["left_shift", "/"]},
            "A": {"func": self._press_hold_release_key, "keys": ["left_shift", "a"]},
            "B": {"func": self._press_hold_release_key, "keys": ["left_shift", "b"]},
            "C": {"func": self._press_hold_release_key, "keys": ["left_shift", "c"]},
            "D": {"func": self._press_hold_release_key, "keys": ["left_shift", "d"]},
            "E": {"func": self._press_hold_release_key, "keys": ["left_shift", "e"]},
            "F": {"func": self._press_hold_release_key, "keys": ["left_shift", "f"]},
            "G": {"func": self._press_hold_release_key, "keys": ["left_shift", "g"]},
            "H": {"func": self._press_hold_release_key, "keys": ["left_shift", "h"]},
            "I": {"func": self._press_hold_release_key, "keys": ["left_shift", "i"]},
            "J": {"func": self._press_hold_release_key, "keys": ["left_shift", "j"]},
            "K": {"func": self._press_hold_release_key, "keys": ["left_shift", "k"]},
            "L": {"func": self._press_hold_release_key, "keys": ["left_shift", "l"]},
            "M": {"func": self._press_hold_release_key, "keys": ["left_shift", "m"]},
            "N": {"func": self._press_hold_release_key, "keys": ["left_shift", "n"]},
            "O": {"func": self._press_hold_release_key, "keys": ["left_shift", "o"]},
            "P": {"func": self._press_hold_release_key, "keys": ["left_shift", "p"]},
            "Q": {"func": self._press_hold_release_key, "keys": ["left_shift", "q"]},
            "R": {"func": self._press_hold_release_key, "keys": ["left_shift", "r"]},
            "S": {"func": self._press_hold_release_key, "keys": ["left_shift", "s"]},
            "T": {"func": self._press_hold_release_key, "keys": ["left_shift", "t"]},
            "U": {"func": self._press_hold_release_key, "keys": ["left_shift", "u"]},
            "V": {"func": self._press_hold_release_key, "keys": ["left_shift", "v"]},
            "W": {"func": self._press_hold_release_key, "keys": ["left_shift", "w"]},
            "X": {"func": self._press_hold_release_key, "keys": ["left_shift", "x"]},
            "Y": {"func": self._press_hold_release_key, "keys": ["left_shift", "y"]},
            "Z": {"func": self._press_hold_release_key, "keys": ["left_shift", "z"]},
        }
        for txt in str(text):
            key_map = sp_key.get(txt, dict(func=self._press_key, keys=[txt]))
            func = key_map.get("func")
            keys = key_map.get("keys")
            func(*keys)

    def _paste_text(self, text: str) -> None:
        """Simulates typing text with paste from clipboard.

        RECOMMEND use this for text field directly typing or another launage typing support.

        Args:
            text (str): text need type
        """
        self._set_clipboard(text=str(text))
        self._press_hold_release_key("ctrl", "v")
        self._empty_clipboard()
