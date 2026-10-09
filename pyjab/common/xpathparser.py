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
        """The attribute predicates on a node, flattened, for existing callers."""
        predicates = XpathParser.get_predicates(node_conditions)
        attributes = []
        for predicate in predicates:
            attributes.extend(predicate.get("attributes", []))
        return attributes

    @staticmethod
    def get_predicates(node_conditions: str) -> list:
        """The node's predicates, in the order they appear, one entry per bracket.

        XPath applies predicates left to right and each one filters what the previous
        left behind, which is why the order is part of the meaning:

            child::para[@type='warning'][position()=5]   the fifth of those with @type
            child::para[position()=5][@type='warning']   the fifth child, if it has @type

        Returning a flat attribute list cannot express that, and the previous version
        refused more than one bracket rather than trying. Each entry here is either

            {"attributes": [...]}   a boolean expression over attributes, and/or
            {"position": 3}         1-based, counted within the parent being searched

        Two forms are rejected rather than approximated: `[position()>1]` and
        `[last()]`, which would need a general expression evaluator. A locator that
        cannot work should say so, not report that the element is missing.
        """
        conditions = re.findall(r"([^\[\]]+)", node_conditions)
        if not conditions:
            return list()

        predicates = []
        for condition in conditions:
            stripped = condition.strip()
            if not stripped:
                continue

            if re.fullmatch(r"\d+", stripped):
                position = int(stripped)
                if position < 1:
                    raise XpathParserException(
                        f"positions are 1-based in XPath, and '{stripped}' is not"
                    )
                predicates.append(dict(position=position))
                continue

            if re.search(r"\b(position|last)\s*\(", stripped):
                raise XpathParserException(
                    f"only a bare position is supported, not '{stripped}'. "
                    "Write [2] rather than [position()=2]; last() is not supported."
                )

            # The comparison first, so `>=` is not read as `>` with a stray `=`.
            pattern = re.compile(
                r"(@\w+?\s*(<=|>=|!=|<|>|=)\s*\w*\(?(\"[\s\S]*?\"|'[\s\S]*?')?\)?)"
            )
            attributes = []
            for match in pattern.finditer(stripped):
                # Whatever stands between the previous predicate and this one is the
                # operator joining them. It used to be discarded, which meant `or` was
                # silently evaluated as `and`: a locator written with it found nothing
                # and reported "no element", which reads as the element being absent
                # rather than the locator being wrong.
                joiner = stripped[:match.start()].strip() if attributes else ""
                operator = "or" if joiner.lower().endswith("or") else "and"
                name, comparison, value = re.split(
                    r"(<=|>=|!=|<|>|=)", match.group(0)[1:], maxsplit=1
                )
                attributes.append(dict(name=name.strip(), value=value,
                                       operator=operator, comparison=comparison))

            if not attributes:
                raise XpathParserException(
                    f"no contents found conditions '{stripped}'"
                )
            predicates.append(dict(attributes=attributes))

        return predicates

    def get_node_information(self, node: str) -> dict:
        node_role = self.get_node_role(node)
        predicates = self.get_predicates(node[len(node_role):])
        attributes = []
        for predicate in predicates:
            attributes.extend(predicate.get("attributes", []))
        return dict(role=node_role, attributes=attributes, predicates=predicates)
