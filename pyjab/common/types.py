from ctypes import c_int, c_int64
from pyjab.common.logger import Logger


class JOBJECT64(c_int64):
    Logger(self.__class__.__name__).info("JOBJECT64")


ACCESSIBLE_TABLE = JOBJECT64

jint=c_int