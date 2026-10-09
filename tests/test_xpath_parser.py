"""Tests for pyjab's XPath subset parser.

``xpathparser`` has no Windows dependency, so unlike most of pyjab it is tested
directly rather than through stand-ins.
"""

import pytest

from pyjab.common.exceptions import XpathParserException
from pyjab.common.xpathparser import XpathParser

# XpathParser is decorated with @singleton, which replaces the class with a
# wrapper function. Class-level access has to go through __wrapped__.
Parser = XpathParser.__wrapped__
split_nodes = Parser.split_nodes


class TestSplitNodes:
    @pytest.mark.parametrize("xpath, expected", [
        ("//internal frame/panel", ["internal frame", "panel"]),
        ("/a", ["a"]),
        # A trailing slash and a doubled inner slash are both tolerated, as
        # they were before; the point of these cases is that the rewrite did not
        # change them.
        ("/a/", ["a"]),
        ("/a//b", ["a", "b"]),
        ("//menu[@name='A Menu']/menu[@name='B']",
         ["menu[@name='A Menu']", "menu[@name='B']"]),
        ("//*[@name='x']", ["*[@name='x']"]),
        ("//panel/panel", ["panel", "panel"]),
    ])
    def test_splits_on_slashes_between_nodes(self, xpath, expected):
        assert split_nodes(xpath) == expected

    @pytest.mark.parametrize("xpath", [
        "//panel[@name='a/b']",
        '//panel[@name="a/b"]',
        "//panel[@name='a/b' and @objectdepth=2]",
    ])
    def test_a_slash_inside_a_quoted_value_is_not_a_separator(self, xpath):
        """Regression: the path used to be split before it was parsed.

        ``//panel[@name='a/b']`` became ``["panel[@name='a", "b']"]``, so the
        locator could never match. Both quote styles are equivalent here.
        """
        nodes = split_nodes(xpath)

        assert len(nodes) == 1
        assert "'a/b'" in nodes[0] or '"a/b"' in nodes[0]

    def test_slash_alone_is_an_error(self):
        """Regression: '/' returned an empty list.

        An empty node list made the callers return None while still declaring a
        JABElement return type, so the failure surfaced far from its cause.
        """
        with pytest.raises(XpathParserException) as excinfo:
            split_nodes("/")

        assert "does not contain a node" in str(excinfo.value)

    @pytest.mark.parametrize("xpath", ["///a", "////a", "a", "", "panel"])
    def test_rejects_malformed_leading_slashes(self, xpath):
        with pytest.raises(XpathParserException):
            split_nodes(xpath)


class TestNodeInformation:
    def test_parses_role_and_attribute(self):
        info = Parser().get_node_information("panel[@name='a/b']")

        assert info["role"] == "panel"
        assert info["attributes"] == [
            {"name": "name", "value": "'a/b'", "operator": "and", "comparison": "="}
        ]

    def test_attribute_value_keeps_its_quotes(self):
        """Callers strip the quotes themselves, so the parser must preserve them."""
        info = Parser().get_node_information("page tab[@name='HSV']")

        assert info["role"] == "page tab"
        assert info["attributes"][0]["value"].startswith("'")

    def test_node_without_conditions_has_no_attributes(self):
        info = Parser().get_node_information("panel")

        assert info["role"] == "panel"
        assert info["attributes"] == []

    def test_wildcard_role(self):
        assert Parser().get_node_information("*")["role"] == "*"

    @pytest.mark.parametrize("node", ["PANEL", "not a role", "panel[0]",
                                      "panel[position()=2]", "panel[last()]"])
    def test_rejects_unparsable_nodes(self, node):
        with pytest.raises(XpathParserException):
            Parser().get_node_information(node)
