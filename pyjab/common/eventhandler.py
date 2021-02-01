from pyjab.common.logger import Logger


class EvenetHandler(object):
    def __init__(self, focus) -> None:
        self.log = Logger(self.__class__.__name__)
        self._last_queue_focus = focus

    @property
    def last_queue_focus(self):
        return self._last_queue_focus

    @last_queue_focus.setter
    def last_queue_focus(self, focus):
        self._last_queue_focus = focus