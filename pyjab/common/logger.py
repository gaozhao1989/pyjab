import logging
from pyjab.common.singleton import singleton


@singleton
class Logger(object):
    LOGGER_INFO = logging.INFO
    LOGGER_DEBUG = logging.DEBUG
    LOGGER_WARN = logging.WARN
    LOGGER_ERROR = logging.ERROR
    LOGGER_CRITICAL = logging.CRITICAL

    def __init__(self, name=None, level=logging.INFO):
        self.FORMAT = "%(asctime)-15s %(levelname)s %(name)s %(message)s"
        self.log = logging.getLogger(name)
        # A library does not configure logging.
        #
        # This used to call `logging.basicConfig`, which configures the **root** logger and
        # does so once, on first import -- so importing pyjab silently decided the format
        # and level for every other logger in the host application, and the host could not
        # tell that it had been decided. The standard answer for a library is a NullHandler:
        # records go nowhere until the application configures logging, which is the
        # application's job and always was.
        #
        # `Logger` is a singleton (see AGENTS.md 2.9), so this runs once per process, and
        # that is exactly why the old behaviour was so hard to notice.
        if not self.log.handlers:
            self.log.addHandler(logging.NullHandler())
        self.log.setLevel(level)

    def info(self, msg, *args, **kwargs):
        self.log.info(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.log.debug(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.log.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.log.critical(msg, *args, **kwargs)
