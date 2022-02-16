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

    def split_nodes(self, xpath: str) -> list:
        if not xpath.startswith("/"):
            raise XpathParserException("xpath should start with '/'")
        nodes = xpath.split("/")
        empty_count = nodes.count("")
        if empty_count not in [1, 2]:
            raise XpathParserException("incorrect '/' numbers")
        return [node for node in nodes if node]

    def get_node_role(self, node: str) -> str:
        pattern = re.compile("^[a-z ]+|^\*")
        content = pattern.search(node)
        try:
            role = content.group()
        except AttributeError:
            raise XpathParserException(f"incorrect role set for node '{node}'")
        if role in Role.__members__.values():
            return role
        elif role == "*":
            return "*"
        else:
            raise XpathParserException(f"incorrect role set '{role}'")

    def get_node_attributes(self, node_conditions: str) -> list:
        pattern = re.compile("([^\[\]]+)")
        conditions = pattern.findall(node_conditions)
        if len(conditions) == 0:
            return list()
        if len(conditions) > 1:
            raise XpathParserException(
                f"extra node conditions found '{conditions}'"
            )
        condition = conditions[0]
        pattern = re.compile("(@\w+?=\s*\w*\(?(\"[\s\S]*?\"|'[\s\S]*?')?\)?)")
        contents = pattern.findall(condition)
        if len(contents) < 1:
            raise XpathParserException(
                f"no contents found conditions '{contents}'"
            )
        attributes = []
        for content in contents:
            name, value = content[0][1:].split(sep="=", maxsplit=1)
            attributes.append(dict(name=name, value=value))
        return attributes

    def get_node_information(self, node: str) -> dict:
        node_role = self.get_node_role(node)
        node_attributes = self.get_node_attributes(node[len(node_role) :])
        return dict(role=node_role, attributes=node_attributes)
