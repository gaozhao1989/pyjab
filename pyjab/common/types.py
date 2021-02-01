from ctypes import c_int, c_int64, CFUNCTYPE, c_long, c_wchar_p


class JOBJECT64(c_int64):
    pass


ACCESSIBLE_TABLE = JOBJECT64

focus_gained_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64)
property_name_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)
property_description_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)
property_value_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)
property_state_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, c_wchar_p, c_wchar_p
)
property_caret_change_fp = CFUNCTYPE(None, c_long, JOBJECT64, JOBJECT64, c_int, c_int)
property_active_descendent_change_fp = CFUNCTYPE(
    None, c_long, JOBJECT64, JOBJECT64, JOBJECT64, JOBJECT64
)
