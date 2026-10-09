import re
from pyjab.common.role import Role
from pyjab.common.exceptions import XpathParserException
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton


# TODO: this is very simple parser, need refactor in future
@singleton
class XpathParser(object):
    def __init__(self) -> None:
        self.logger = Logger("pyjab")

    @staticmethod
    def split_nodes(xpath: str) -> list:
        """Split an xpath into its node path.

        Slashes inside a quoted value are part of the value, not separators:
        ``//panel[@name='a/b']`` is one node, not two. A path that contains no
        node at all -- ``/`` -- is an error rather than an empty list, because
        every caller treats an empty result as "no element found" and returns
        ``None``, which then contradicts their declared return type.
        """
        if not xpath.startswith("/"):
            raise XpathParserException("xpath should start with '/'")

        leading_slashes = len(xpath) - len(xpath.lstrip("/"))
        if leading_slashes not in (1, 2):
            raise XpathParserException(
                f"incorrect '/' numbers: xpath '{xpath}' should start with "
                "'/' or '//'"
            )

        nodes = []
        current = []
        quote = ""
        for char in xpath:
            if quote:
                if char == quote:
                    quote = ""
                current.append(char)
            elif char in "\"'":
                quote = char
                current.append(char)
            elif char == "/":
                if current:
                    nodes.append("".join(current))
                    current = []
            else:
                current.append(char)
        if current:
            nodes.append("".join(current))

        if not nodes:
            raise XpathParserException(f"xpath '{xpath}' does not contain a node")
        return nodes

    @staticmethod
    def get_node_role(node: str) -> str:
        pattern = re.compile(r"^[a-z ]+|^\*")
        content = pattern.search(node)
        try:
            role = content.group()
        except AttributeError as e:
            raise XpathParserException(f"incorrect role set for node '{node}'") from e
        if role in Role.__members__.values():
            return role
        elif role == "*":
            return "*"
        else:
            raise XpathParserException(f"incorrect role set '{role}'")

    @staticmethod
    def get_node_attributes(node_conditions: str) -> list:
        pattern = re.compile(r"([^\[\]]+)")
        conditions = pattern.findall(node_conditions)
        if len(conditions) == 0:
            return list()
        if len(conditions) > 1:
            raise XpathParserException(
                f"extra node conditions found '{conditions}'"
            )
        condition = conditions[0]
        pattern = re.compile(r"(@\w+?=\s*\w*\(?(\"[\s\S]*?\"|'[\s\S]*?')?\)?)")

        attributes = []
        for match in pattern.finditer(condition):
            # Whatever stands between the previous predicate and this one is the
            # operator joining them. It used to be discarded, which meant `or` was
            # silently evaluated as `and`: a locator written with it found nothing
            # and reported "no element", which reads as the element being absent
            # rather than the locator being wrong.
            joiner = condition[:match.start()].strip() if attributes else ""
            operator = "or" if joiner.lower().endswith("or") else "and"
            name, value = match.group(0)[1:].split(sep="=", maxsplit=1)
            attributes.append(dict(name=name, value=value, operator=operator))

        if not attributes:
            raise XpathParserException(
                f"no contents found conditions '{condition}'"
            )
        return attributes

    def get_node_information(self, node: str) -> dict:
        node_role = self.get_node_role(node)
        node_attributes = self.get_node_attributes(node[len(node_role):])
        return dict(role=node_role, attributes=node_attributes)
