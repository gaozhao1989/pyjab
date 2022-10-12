import re
from pyjab.jab.role import Role
from pyjab.common.exceptions import XpathParserException
from pyjab.common.logger import Logger
from pyjab.common.singleton import singleton


@singleton
class XpathParser(object):
    def __init__(self) -> None:
        self.logger = Logger("pyjab")

    def get_nodes(self, xpath: str) -> list[str]:
        """Get list of node from string of Xpath.

        Args:
            xpath (str): Xpath locator string.

        Raises:
            XpathParserException:
                1. Xpath string not start with '/'.
                2. Xpath node with '/' number not equals 1 or 2.

        Returns:
            list (str): List of node string.
        """
        if not xpath.startswith(("/", "//")):
            raise XpathParserException(
                "Invalid Xpath, Please check Xpath should be start with '/' or '//'"
            )
        nodes = [node for node in xpath.split("/") if node]
        self.logger.debug(f"Get nodes => {nodes}")
        return nodes

    def get_node(self, node: str) -> str:
        """Get node text(Role) from node string.

        Args:
            node (str): Node string from func 'get_nodes'.

        Raises:
            XpathParserException:
                1. No search result of matched node role string.
                2. Node not matched with in Class ROLE or '*'.
                3. Node not matched with string '.' or '..'.

        Returns:
            str: Node text(Role).
        """
        pattern = re.compile("^[a-z. ]+|^\*")
        match = pattern.search(node)
        if match is None:
            raise XpathParserException(f"Invalid Node '{node}'")
        txt = match.group()
        if any([txt in Role.__members__.values(), txt in ("*", ".", "..")]):
            self.logger.debug(f"Get Node text => {txt}")
            return txt
        else:
            raise XpathParserException(
                f"Invalid Node text '{txt}', text should be in Role or match with '*', '.', '..'"
            )

    @staticmethod
    def parse_predicates(predicates: str) -> list:
        """Get node attributes from node predicates.

        Notice:
            predicates means content in '[]'.

        Args:
            predicates (str): Node predicates from xpath.

        Raises:
            XpathParserException: _description_
            XpathParserException: _description_

        Returns:
            list: _description_
        """
        pattern = re.compile("([^\[\]]+)")
        predicates = pattern.findall(predicates)
        if len(predicates) == 0:
            return list()
        if len(predicates) > 1:
            raise XpathParserException(f"Invalid node predicates '{predicates}'")
        predicate = predicates[0]
        pattern = re.compile("(@\w+?=\s*\w*\(?(\"[\s\S]*?\"|'[\s\S]*?')?\)?)")
        contents = pattern.findall(predicate)
        if len(contents) < 1:
            raise XpathParserException(f"no contents found conditions '{contents}'")
        attributes = []
        for content in contents:
            name, value = content[0][1:].split(sep="=", maxsplit=1)
            attributes.append(dict(name=name, value=value))
        return attributes

    def get_node_information(self, node: str) -> dict:
        node_role = self.get_node(node)
        node_attributes = self.parse_predicates(node[len(node_role) :])
        return dict(role=node_role, attributes=node_attributes)
