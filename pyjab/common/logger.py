import logging
from typing import Optional
from pyjab.common.singleton import singleton


@singleton
class LoggerFormatter(logging.Formatter):

    BLACK = "\033[30m"
    RED = "\033[31m"
    BOLD_RED = "\033[91m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    DEFAULT = "\033[39m"
    RESET = "\033[0m"

    FORMAT = "%(asctime)-15s %(levelname)s %(name)s %(message)s"

    DICT_LOG_COLOR = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARN: YELLOW,
        logging.ERROR: RED,
        logging.FATAL: BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        log_format = (
            self.DICT_LOG_COLOR.get(record.levelno, "") + self.FORMAT + self.RESET
        )
        return logging.Formatter(log_format).format(record)


@singleton
class Logger(object):
    def __init__(self, name: Optional[str] = None, level: int = logging.DEBUG) -> None:
        # Return a logger with the specified name, creating it if necessary.
        self.logger = logging.getLogger(name)
        # Set the logging level of this logger
        self.logger.setLevel(level)
        # Create Console handler
        self.handler = logging.StreamHandler()
        # Set the logging level of this handler
        self.handler.setLevel(level)
        # Set the formatter for this handler
        self.handler.setFormatter(LoggerFormatter())
        self.logger.addHandler(self.handler)

    def debug(self, msg, *args, **kwargs) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs) -> None:
        self.logger.warn(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs) -> None:
        self.logger.error(msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs) -> None:
        self.logger.fatal(msg, *args, **kwargs)
