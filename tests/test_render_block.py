"""Unit tests for render_block() dispatch and individual block renderers."""

import tkinter as tk

import pytest

from kiro_acp_chat_client.markdown_renderer import (
    Block,
    render_block,
    setup_tags,
)


@pytest.fixture
def text_widget():
    """Create a tk.Text widget for testing."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available")
    widget = tk.Text(root)
    setup_tags(widget)
    yield widget
    root.destroy()


def _get_text(widget: tk.Text) -> str:
    """Get all text from widget (strip trailing newline added by tk)."""
    return widget.get("1.0", tk.END).rstrip("\n")


def _get_tags_at(widget: tk.Text, index: str) -> tuple:
    """Get tags at a specific index."""
    return widget.tag_names(index)


class TestHeaderRenderer:
    def test_header_renders_content_without_hash(self, text_widget):
        block = Block(kind="header", content="Hello World", level=1)
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "Hello World" in text
        assert "#" not in text

    def test_header_applies_level_tag(self, text_widget):
        block = Block(kind="header", content="Title", level=2)
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_h2" in tags
        assert "base" in tags

    def test_header_inline_formatting(self, text_widget):
        block = Block(kind="header", content="Hello **bold**", level=1)
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "Hello bold" in text
        assert "**" not in text


class TestCodeBlockRenderer:
    def test_code_block_renders_content(self, text_widget):
        block = Block(kind="code", content="print('hello')\nprint('world')")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "print('hello')" in text
        assert "print('world')" in text

    def test_code_block_applies_tag(self, text_widget):
        block = Block(kind="code", content="x = 1")
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_code_block" in tags
        assert "base" in tags

    def test_code_block_no_inline_parsing(self, text_widget):
        block = Block(kind="code", content="**not bold** `not code`")
        render_block(text_widget, block, base_tag="")
        text = _get_text(text_widget)
        # Delimiters should be preserved (no inline parsing)
        assert "**not bold**" in text
        assert "`not code`" in text


class TestUnorderedListRenderer:
    def test_ulist_renders_bullet(self, text_widget):
        block = Block(kind="ulist", content="item one", meta={"levels": [1]})
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "\u2022 item one" in text

    def test_ulist_multiple_items(self, text_widget):
        block = Block(
            kind="ulist",
            content="first\nsecond\nthird",
            meta={"levels": [1, 1, 1]},
        )
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "\u2022 first" in text
        assert "\u2022 second" in text
        assert "\u2022 third" in text

    def test_ulist_applies_level_tags(self, text_widget):
        block = Block(
            kind="ulist",
            content="level1\nlevel2",
            meta={"levels": [1, 2]},
        )
        render_block(text_widget, block, base_tag="base")
        tags_line1 = _get_tags_at(text_widget, "1.0")
        assert "md_list_1" in tags_line1

    def test_ulist_caps_level_at_3(self, text_widget):
        block = Block(
            kind="ulist",
            content="deep",
            meta={"levels": [5]},
        )
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_list_3" in tags

    def test_ulist_inline_formatting(self, text_widget):
        block = Block(kind="ulist", content="**bold** item", meta={"levels": [1]})
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "bold item" in text
        assert "**" not in text


class TestOrderedListRenderer:
    def test_olist_renders_numbers(self, text_widget):
        block = Block(
            kind="olist",
            content="first\nsecond\nthird",
            meta={"levels": [1, 1, 1]},
        )
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "1. first" in text
        assert "2. second" in text
        assert "3. third" in text

    def test_olist_applies_level_tags(self, text_widget):
        block = Block(kind="olist", content="item", meta={"levels": [2]})
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_list_2" in tags

    def test_olist_inline_formatting(self, text_widget):
        block = Block(kind="olist", content="*italic* step", meta={"levels": [1]})
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "italic step" in text
        assert "*" not in text


class TestBlockquoteRenderer:
    def test_blockquote_renders_content(self, text_widget):
        block = Block(kind="blockquote", content="quoted text")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "quoted text" in text

    def test_blockquote_applies_tag(self, text_widget):
        block = Block(kind="blockquote", content="quote")
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_blockquote" in tags
        assert "base" in tags

    def test_blockquote_multiline(self, text_widget):
        block = Block(kind="blockquote", content="line1\nline2")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "line1" in text
        assert "line2" in text

    def test_blockquote_inline_formatting(self, text_widget):
        block = Block(kind="blockquote", content="**bold** quote")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "bold quote" in text
        assert "**" not in text


class TestTableRenderer:
    def test_table_renders_header_and_data(self, text_widget):
        content = "| Name | Age |\n| --- | --- |\n| Alice | 30 |"
        block = Block(kind="table", content=content)
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "Name" in text
        assert "Age" in text
        assert "Alice" in text
        assert "30" in text

    def test_table_omits_separator_row(self, text_widget):
        content = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        block = Block(kind="table", content=content)
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "---" not in text

    def test_table_header_has_header_tag(self, text_widget):
        content = "| H1 | H2 |\n| --- | --- |\n| D1 | D2 |"
        block = Block(kind="table", content=content)
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_table_header" in tags

    def test_table_data_has_table_tag(self, text_widget):
        content = "| H1 | H2 |\n| --- | --- |\n| D1 | D2 |"
        block = Block(kind="table", content=content)
        render_block(text_widget, block, base_tag="base")
        # Data row starts on line 2
        tags = _get_tags_at(text_widget, "2.0")
        assert "md_table" in tags


class TestHorizontalRuleRenderer:
    def test_hrule_renders_separator(self, text_widget):
        block = Block(kind="hrule", content="")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "\u2500" in text
        assert len(text.strip()) == 32

    def test_hrule_applies_tag(self, text_widget):
        block = Block(kind="hrule", content="")
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "md_hrule" in tags
        assert "base" in tags


class TestParagraphRenderer:
    def test_paragraph_renders_content(self, text_widget):
        block = Block(kind="paragraph", content="Hello world")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "Hello world" in text

    def test_paragraph_applies_base_tag(self, text_widget):
        block = Block(kind="paragraph", content="text")
        render_block(text_widget, block, base_tag="base")
        tags = _get_tags_at(text_widget, "1.0")
        assert "base" in tags

    def test_paragraph_inline_formatting(self, text_widget):
        block = Block(kind="paragraph", content="**bold** and *italic*")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "bold and italic" in text
        assert "**" not in text
        assert "*" not in text


class TestRenderBlockDispatch:
    def test_unknown_kind_falls_back_to_paragraph(self, text_widget):
        block = Block(kind="unknown_type", content="fallback text")
        render_block(text_widget, block, base_tag="base")
        text = _get_text(text_widget)
        assert "fallback text" in text

    def test_no_base_tag(self, text_widget):
        block = Block(kind="paragraph", content="no base")
        render_block(text_widget, block, base_tag="")
        text = _get_text(text_widget)
        assert "no base" in text
