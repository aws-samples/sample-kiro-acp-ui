"""Quick verification that the markdown_renderer module skeleton is correct."""

import tkinter as tk

import pytest

from kiro_acp_chat_client.markdown_renderer import (
    MARKDOWN_TAGS,
    Block,
    render_markdown,
    setup_tags,
)


def _make_root():
    """Try to create a Tk root; skip test if display unavailable."""
    try:
        root = tk.Tk()
        root.withdraw()
        return root
    except tk.TclError:
        pytest.skip("Tkinter display not available")


def test_markdown_tags_contains_all_expected_keys():
    expected_tags = [
        "md_h1",
        "md_h2",
        "md_h3",
        "md_h4",
        "md_h5",
        "md_h6",
        "md_bold",
        "md_italic",
        "md_bold_italic",
        "md_inline_code",
        "md_code_block",
        "md_list_1",
        "md_list_2",
        "md_list_3",
        "md_blockquote",
        "md_table",
        "md_table_header",
        "md_link",
        "md_hrule",
    ]
    for tag in expected_tags:
        assert tag in MARKDOWN_TAGS, f"Missing tag: {tag}"


def test_setup_tags_configures_widget():
    root = _make_root()
    try:
        text_widget = tk.Text(root)
        setup_tags(text_widget)
        # Verify tags were configured by checking one tag's properties
        font = text_widget.tag_cget("md_h1", "font")
        assert "bold" in font or "18" in font
        bg = text_widget.tag_cget("md_code_block", "background")
        assert bg == "#f5f5f5"
        underline = text_widget.tag_cget("md_link", "underline")
        assert str(underline) == "1"  # handle both string and integer return types from tkinter
    finally:
        root.destroy()


def test_block_dataclass_fields():
    block = Block(kind="paragraph", content="Hello world")
    assert block.kind == "paragraph"
    assert block.content == "Hello world"
    assert block.level == 0
    assert block.meta == {}

    block_with_meta = Block(kind="code", content="print(1)", level=0, meta={"lang": "python"})
    assert block_with_meta.meta == {"lang": "python"}


def test_render_markdown_accepts_correct_args():
    root = _make_root()
    try:
        text_widget = tk.Text(root)
        # Should not raise
        render_markdown(text_widget, "# Hello")
        render_markdown(text_widget, "**bold**", base_tag="assistant_msg")
        # Function renders content into the widget
        content = text_widget.get("1.0", tk.END).strip()
        assert "Hello" in content
        assert "bold" in content
    finally:
        root.destroy()
