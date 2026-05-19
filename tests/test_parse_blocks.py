"""Unit tests for parse_blocks() function."""

import pytest
from kiro_acp_chat_client.markdown_renderer import Block, parse_blocks


class TestEmptyInput:
    def test_empty_string_returns_empty_list(self):
        assert parse_blocks("") == []

    def test_whitespace_only_returns_empty_list(self):
        # Lines with only whitespace are stripped and treated as empty
        assert parse_blocks("   \n   \n   ") == []


class TestFencedCodeBlocks:
    def test_basic_code_block(self):
        content = "```\nprint('hello')\n```"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].content == "print('hello')"
        assert blocks[0].meta == {}

    def test_code_block_with_language(self):
        content = "```python\ndef foo():\n    pass\n```"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].content == "def foo():\n    pass"
        assert blocks[0].meta == {"lang": "python"}

    def test_unclosed_code_block(self):
        content = "```javascript\nconst x = 1;\nconst y = 2;"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].content == "const x = 1;\nconst y = 2;"
        assert blocks[0].meta == {"lang": "javascript"}

    def test_code_block_preserves_internal_content(self):
        content = "```\n# This is not a header\n- Not a list\n> Not a quote\n```"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert "# This is not a header" in blocks[0].content

    def test_code_block_with_more_backticks(self):
        content = "````\nsome code\n````"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].content == "some code"

    def test_empty_code_block(self):
        content = "```\n```"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].content == ""


class TestHeaders:
    def test_h1(self):
        blocks = parse_blocks("# Hello World")
        assert len(blocks) == 1
        assert blocks[0].kind == "header"
        assert blocks[0].content == "Hello World"
        assert blocks[0].level == 1

    def test_h2(self):
        blocks = parse_blocks("## Section")
        assert len(blocks) == 1
        assert blocks[0].level == 2

    def test_h3(self):
        blocks = parse_blocks("### Subsection")
        assert len(blocks) == 1
        assert blocks[0].level == 3

    def test_h6(self):
        blocks = parse_blocks("###### Deep")
        assert len(blocks) == 1
        assert blocks[0].level == 6
        assert blocks[0].content == "Deep"

    def test_hash_without_space_is_paragraph(self):
        blocks = parse_blocks("#NoSpace")
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"

    def test_hash_midline_is_paragraph(self):
        blocks = parse_blocks("This has a # in it")
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"
        assert blocks[0].content == "This has a # in it"

    def test_seven_hashes_is_paragraph(self):
        blocks = parse_blocks("####### Too many")
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"


class TestHorizontalRules:
    def test_three_dashes(self):
        blocks = parse_blocks("---")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_three_asterisks(self):
        blocks = parse_blocks("***")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_three_underscores(self):
        blocks = parse_blocks("___")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_more_than_three(self):
        blocks = parse_blocks("-----")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_with_spaces_between(self):
        blocks = parse_blocks("- - -")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_asterisks_with_spaces(self):
        blocks = parse_blocks("* * *")
        assert len(blocks) == 1
        assert blocks[0].kind == "hrule"

    def test_two_dashes_is_not_hrule(self):
        # Two dashes is not enough
        blocks = parse_blocks("--")
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"


class TestUnorderedLists:
    def test_dash_list(self):
        content = "- Item 1\n- Item 2\n- Item 3"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "ulist"
        assert "Item 1" in blocks[0].content
        assert "Item 2" in blocks[0].content
        assert "Item 3" in blocks[0].content

    def test_asterisk_list(self):
        content = "* First\n* Second"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "ulist"

    def test_plus_list(self):
        content = "+ A\n+ B"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "ulist"

    def test_nested_list_levels(self):
        content = "- Level 1\n   - Level 2\n      - Level 3"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "ulist"
        assert blocks[0].meta["levels"] == [1, 2, 3]

    def test_indent_level_boundaries(self):
        content = "- Zero indent\n  - Two spaces\n   - Three spaces\n      - Six spaces"
        blocks = parse_blocks(content)
        assert blocks[0].meta["levels"] == [1, 1, 2, 3]


class TestOrderedLists:
    def test_basic_ordered_list(self):
        content = "1. First\n2. Second\n3. Third"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "olist"
        assert "First" in blocks[0].content
        assert "Second" in blocks[0].content

    def test_multi_digit_numbers(self):
        content = "10. Tenth item\n11. Eleventh"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "olist"

    def test_indented_ordered_list(self):
        content = "1. Top\n   1. Nested"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].meta["levels"] == [1, 2]


class TestBlockquotes:
    def test_single_blockquote(self):
        blocks = parse_blocks("> This is quoted")
        assert len(blocks) == 1
        assert blocks[0].kind == "blockquote"
        assert blocks[0].content == "This is quoted"

    def test_consecutive_blockquotes_grouped(self):
        content = "> Line 1\n> Line 2\n> Line 3"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "blockquote"
        assert "Line 1\nLine 2\nLine 3" == blocks[0].content

    def test_blockquote_with_empty_prefix(self):
        content = "> First\n>\n> Third"
        blocks = parse_blocks(content)
        # All grouped since they all start with >
        assert len(blocks) == 1
        assert blocks[0].kind == "blockquote"


class TestTableRows:
    def test_basic_table(self):
        content = "| Col1 | Col2 |\n|------|------|\n| A    | B    |"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "table"
        assert "Col1" in blocks[0].content
        assert "A" in blocks[0].content

    def test_consecutive_table_rows_grouped(self):
        content = "| H1 | H2 |\n| -- | -- |\n| D1 | D2 |\n| D3 | D4 |"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "table"


class TestParagraphs:
    def test_plain_text(self):
        blocks = parse_blocks("Hello world")
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"
        assert blocks[0].content == "Hello world"

    def test_consecutive_lines_grouped(self):
        content = "Line one\nLine two"
        blocks = parse_blocks(content)
        assert len(blocks) == 1
        assert blocks[0].kind == "paragraph"
        assert blocks[0].content == "Line one\nLine two"

    def test_empty_line_separates_paragraphs(self):
        content = "Para one\n\nPara two"
        blocks = parse_blocks(content)
        assert len(blocks) == 2
        assert blocks[0].content == "Para one"
        assert blocks[1].content == "Para two"


class TestMixedContent:
    def test_header_then_paragraph(self):
        content = "# Title\nSome text here"
        blocks = parse_blocks(content)
        assert len(blocks) == 2
        assert blocks[0].kind == "header"
        assert blocks[1].kind == "paragraph"

    def test_full_document(self):
        content = "# Title\n\nSome intro text.\n\n- Item 1\n- Item 2\n\n```python\ncode()\n```\n\n---\n\n> A quote"
        blocks = parse_blocks(content)
        kinds = [b.kind for b in blocks]
        assert "header" in kinds
        assert "paragraph" in kinds
        assert "ulist" in kinds
        assert "code" in kinds
        assert "hrule" in kinds
        assert "blockquote" in kinds
