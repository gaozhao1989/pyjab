class InvalidJABElement(RuntimeError):
    """
    Raised by NVDAObjects during construction to inform that this object is invalid.
    """


class JABException(Exception):
    """
    Raised by Java Access Bridge if func internal error
    """

    def __init__(self, message: str = None, status: str = None) -> None:
        super().__init__(message, status)
        self.message = message
        self.status = status