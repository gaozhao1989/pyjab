from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Union
from pyjab.common.exceptions import JABException
from pyjab.common.logger import Logger


class JABDriverWait(object):

    def __init__(self, timeout: Union[int, float], ignored_exceptons: Iterable = (JABException,)) -> None:
        self.logger = Logger("pyjab")
        self.timeout = timeout
        self.ignored_exceptions = tuple(ignored_exceptons)

    def until(self, func: Callable, *args, **kwargs):
        try:
            future = ThreadPoolExecutor().submit(func, *args, **kwargs)
            return future.result(self.timeout)
        except self.ignored_exceptions as exc:
            self.logger.warn(f"Ignore exception {exc}")
