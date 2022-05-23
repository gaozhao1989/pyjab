"""
The By implementation.
"""


class By(object):
    """
    Set of supported locator strategies.
    """

    XPATH = "xpath"
    NAME = "name"
    DESCRIPTION = "description"
    ROLE = "role"
    STATES = "states"
    OBJECT_DEPTH = "objectdepth"
    CHILDREN_COUNT = "childrencount"
    INDEX_IN_PARENT = "indexinparent"
