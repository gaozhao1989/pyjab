"""
The By implementation.
"""


class By(object):
    """
    Set of supported locator strategies.
    """

    XPATH = "xpath"
    NAME = "name"
    ROLE = "role"
    STATES = "states"
    OBJECT_DEPTH = "object_depth"
    CHILDREN_COUNT = "children_count"
    INDEX_IN_PARENT = "index_in_parent"
