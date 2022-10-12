import unittest

class TestXpathParser(unittest.TestCase):
    # reference with URL: https://devhints.io/xpath

    def test_descendant_selectors(self):
        # all matched node with node "panel"
        xpath = "//panel"
        # all matched node "text" under parent node "panel"
        xpath = "//panel//text"
        # all matched node "text" under directly parent node "panel"
        xpath = "//panel/text"
        # all matched node "list" under directly parent node "combo box" of directly parent node "panel" 
        xpath = "//panel/combo box/list"
        # any node under directly parent node "panel"
        xpath = "//panel/*"
        # root/current parent node
        xpath = "/"
        # node "panel" under root/current parent node
        xpath = "/panel"

    def test_attribute_selectors(self):
        # any node with attribute "name" equals to "test"
        xpath = "//*[@name='test']"
        # any node "text" with attribute "description" equals to "text field"
        xpath = "//text[@description='text field']"
        # any node "text" with attribute "name" of string start with "test", works with @name, @description and text()
        xpath = "//text[starts-with(@name, 'test')]"
        # any node "text" with attribute "name" of string end with "test", works with @name, @description and text()
        xpath = "//text[ends-with(@name, 'test')]"
        # any node "text" with attribute "name" of string comntains with "test", works with @name, @description and text()
        xpath = "//text[contains(@name, 'test')]"

    def test_order_selectors(self):
        # any matched 1st index parent of node "text" under directly parent node "panel"
        xpath = "//panel/text[1]"
        # any matched 2nd index parent of node "text" under directly parent node "panel"
        xpath = "//panel/text[2]"
        # any matched last node "text" under directly parent node "panel"
        xpath = "//panel/text[last()]"
        # 1st "text" with attribute "name" equals "test"
        xpath = "//text[1][@name='test']"
        





    def test_empty_predicate(self):
        pred = ""
        pred = "[]"

    def test_single_predicate(self):
        pred = "[1]" # find 1st
        pred = "[2]" # find 2nd
        pred = "[position()=2]" # find 2nd, equals "[2]"
        pred = "[last()]"   # find last
        pred = "[@name='foo']"
        pred = "[@indexinparent=0]"
        pred = "[@objectdepth < 9]"
        pred = "[@objectdepth >= 10]"
        pred = "[@objectdepth < 10]"
        pred = "[@role!='text']"
        pred = "[starts-with(@states, 'foo')]"
        pred = "[ends-with(@description, 'bar')]"
        pred = "[contains(@name, 'foo')]"
        pred = "[text()='foo']"
    
    def test_multiple_predicate(self):
        pred = "[2 and @name='foo']"
        pred = "[@name='foo' or @name='bar']"
        pred = "[1 and @name='foo' or objectdepth !=5]"