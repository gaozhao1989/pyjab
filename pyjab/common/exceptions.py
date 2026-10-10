class CommonException(Exception):
    """The base of every error pyjab raises.

    ``status`` is kept as an attribute and deliberately **not** passed to
    ``Exception.__init__``.  Passing it there gave every exception two ``args``, so
    ``str(exception)`` was the repr of a tuple::

        str(JABException("Save not found"))  ==  "('Save not found', None)"

    Every message a user printed with ``print(e)``, every one that reached a log line,
    and every one quoted in an issue read that way.  A second argument to an exception
    is not a status channel; it is a second value in the same tuple.
    """

    def __init__(self, message: str = None, status: str = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class JABException(CommonException):
    """
    Raised by Java Access Bridge if func internal error
    """

    pass


class XpathParserException(CommonException):
    """
    Raised by Xpath Parser if error
    """

    pass
