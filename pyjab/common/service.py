from ctypes import cdll
from ctypes import CDLL

from pyjab.config import BRIDGE_DLL


class Service(object):

    def load_library(self)->CDLL:
        return cdll.LoadLibrary(BRIDGE_DLL)