from typing import Optional, Sequence


class JABDriverException(Exception):
    """Base JABDriver exceptions.

    Attributes:

    """

    def __init__(
        self, message: Optional[str] = None, screen: Optional[str] = None, stacktrace: Optional[Sequence[str]] = None
    ) -> None:
        super().__init__()
        self.msg = message
        self.screen = screen
        self.stacktrace = stacktrace

    def __str__(self) -> str:
        exception_msg = f"Message: {self.msg}\n"
        if self.screen:
            exception_msg += "Screenshot: available via screen\n"
        if self.stacktrace:
            stacktrace = "\n".join(self.stacktrace)
            exception_msg += f"Stacktrace:\n{stacktrace}"
        return exception_msg


class JABException(JABDriverException):
    # TODO: Legacy exception, removed in pyjab 1.2.0
    """Legacy exception, will be removed in pyjab 1.2.0"""

    def __init__(self, message: Optional[str] = None, screen: Optional[str] = None, stacktrace: Optional[Sequence[str]] = None) -> None:
        super().__init__(message, screen, stacktrace)

    def __str__(self) -> str:
        return "Legacy exception, will be removed in pyjab 1.2.0. Use JABDriverException instead."


class InvalidSwitchToTargetException(JABDriverException):
    """Thrown when window target to be switched doesn't exist."""


class NoSuchWindowException(InvalidSwitchToTargetException):
    """Thrown when window target to be switched doesn't exist.
    To find the current set of active window handles, you can get a list
    of the active window handles in the following way::
        driver.window_handles
    """


class NoSuchElementException(JABDriverException):
    """Thrown when element could not be found.
    If you encounter this exception, you may want to check the following:
        * Check your selector used in your find_by...
        * Element may not yet be on the screen at the time of the find operation,
          (java window is still loading) see pyjab.common.wait.JABDriverWait()
          for how to write a wait wrapper to wait for an element to appear.
    """


class InvalidElementStateException(JABDriverException):
    """Thrown when a command could not be completed because the element is in
    an invalid state.
    """


class ElementNotVisibleException(InvalidElementStateException):
    """Thrown when an element is present on the DOM, but it is not visible, and
    so is not able to be interacted with.
    Most commonly encountered when trying to click or read text of an
    element that is hidden from view.
    """


class ElementNotInteractableException(InvalidElementStateException):
    """Thrown when an element is present in the DOM but interactions with that
    element will hit another element due to paint order."""


class ElementNotSelectableException(InvalidElementStateException):
    """Thrown when trying to select an unselectable element.
    For example, selecting a 'script' element.
    """


class TimeoutException(JABDriverException):
    """Thrown when a command does not complete in enough time."""


class MoveTargetOutOfBoundsException(JABDriverException):
    """Thrown when the target provided to the `ActionsChains` move() method is
    invalid, i.e. out of document."""


class InvalidSelectorException(JABDriverException):
    """Thrown when the combo box which is used to find an element does not
    return a WebElement.
    Currently this only happens when the combo box is an xpath expression
    and it is either syntactically invalid (i.e. it is not a xpath
    expression) or the expression does not combo box JABElement.
    """


class ScreenshotException(JABDriverException):
    """A screen capture was made impossible."""


class ElementClickInterceptedException(JABDriverException):
    """The Element Click command could not be completed because the element
    receiving the events is obscuring the element that was requested to be
    clicked."""


class XpathParserException(JABDriverException):
    """Xpath value parser is incorrect or not available."""
