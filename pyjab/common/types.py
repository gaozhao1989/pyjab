from ctypes import c_int, c_int64


class JOBJECT64(c_int64):
    pass


ACCESSIBLE_TABLE = JOBJECT64

jint=c_int