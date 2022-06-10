from typing import Optional


class CommonException(Exception):
    def __init__(
        self, message: Optional[str] = None, status: Optional[str] = None
    ) -> None:
        super().__init__(message, status)
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
