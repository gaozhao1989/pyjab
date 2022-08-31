from ctypes import c_bool, c_char, c_float, c_int, c_int64


class JOBJECT64(c_int64):
    pass


class AccessibleContext(JOBJECT64):
    pass


class jint(c_int):
    pass

class jfloat(c_float):
    pass

class jboolean(c_bool):
    pass

class jchar(c_char):
    pass