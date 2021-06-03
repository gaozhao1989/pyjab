import logging


class Logger(object):
    LOGGER_INFO = logging.INFO
    LOGGER_DEBUG = logging.DEBUG
    LOGGER_WARN = logging.WARN
    LOGGER_ERROR = logging.ERROR
    LOGGER_CRITICAL = logging.CRITICAL

    def __init__(self, name=None, level=logging.INFO):
        self.FORMAT = "%(asctime)-15s %(levelname)s %(name)s %(message)s"
        self.log = logging.getLogger(name)
        logging.basicConfig(format=self.FORMAT, level=level)

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
