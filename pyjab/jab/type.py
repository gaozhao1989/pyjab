from ctypes import c_bool, c_char, c_float, c_int, c_int64


class JOBJECT64(c_int64):
    pass


class AccessibleContext(JOBJECT64):
    pass

class AccessibleText(AccessibleContext):
    pass

class AccessibleTable(AccessibleContext):
    pass

class AccessibleHypertext(AccessibleContext):
    pass

class AccessibleValue(AccessibleContext):
    pass

class AccessibleSelection(AccessibleContext):
    pass

class AccessibleHyperlink(AccessibleContext):
    pass

class jint(c_int):
    pass

class jfloat(c_float):
    pass

class jboolean(c_bool):
    pass

class jchar(c_char):
    pass