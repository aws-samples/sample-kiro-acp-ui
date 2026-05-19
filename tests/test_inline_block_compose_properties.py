"""Property-based tests for inline formatting composing with block contexts.

# Feature: markdown-rendering, Property 3: Inline formatting composes with block contexts

**Validates: Requirements 1.2, 6.2, 7.2**
"""

import pytest
import tkinter as tk

from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import Block, render_block, setup_tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_root = None
_widget = None


def _get_widget():
    """Get or create a tk.Text widget for testing; skip if display unavailable."""
    global _root, _widget
    if _root is None:
        try:
            _root = tk.Tk()
            _root.withdraw()
        except tk.TclError:
            try:
                _root = tk.Tk()
                _root.withdraw()
            except tk.TclError:
                pytest.skip("Tkinter display not available")
        _widget = tk.Text(_root)
        setup_tags(_widget)
    return _widget


def _clear_widget(widget):
    """Clear all content from the widget."""
    widget.delete("1.0", tk.END)


def _get_text(widget):
    """Get all text content from widget (strip trailing newline)."""
    return widget.get("1.0", tk.END).rstrip("\n")


def _get_tags_at(widget, index):
    """Get tags applied at a specific index."""
    return widget.tag_names(index)


def _find_text_index(widget, search_text):
    """Find the index of search_text in the widget. Returns None if not found."""
    idx = widget.search(search_text, "1.0", tk.END)
    return idx if idx else None


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Text content that does not contain markdown delimiter characters
safe_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`[]()\\#>|-+\n\r",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")

# Block context types
block_context = st.sampled_from(["ulist", "olist", "blockquote", "paragraph"])

# Inline formatting types: (open_delim, close_delim, expected_inline_tag)
inline_formatting = st.sampled_from([
    ("**", "**", "md_bold"),
    ("*", "*", "md_italic"),
    ("`", "`", "md_inline_code"),
])


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    content=safe_text,
    block_type=block_context,
    fmt_data=inline_formatting,
)
def test_inline_formatting_composes_with_block_contexts(content, block_type, fmt_data):
    """Property 3: Inline formatting composes with block contexts.

    For any block context (list item, blockquote, paragraph) containing valid
    inline formatting (bold, italic, code), the renderer SHALL apply both the
    block-level tag and the inline formatting tag to the affected text segments.

    # Feature: markdown-rendering, Property 3: Inline formatting composes with block contexts

    **Validates: Requirements 1.2, 6.2, 7.2**
    """
    open_delim, close_delim, expected_inline_tag = fmt_data

    # Construct the block content with inline formatting
    formatted_content = f"{open_delim}{content}{close_delim}"

    widget = _get_widget()
    _clear_widget(widget)

    # Build the Block object based on block type
    if block_type == "ulist":
        block = Block(kind="ulist", content=formatted_content, level=1, meta={"levels": [1]})
        expected_block_tag = "md_list_1"
    elif block_type == "olist":
        block = Block(kind="olist", content=formatted_content, level=1, meta={"levels": [1]})
        expected_block_tag = "md_list_1"
    elif block_type == "blockquote":
        block = Block(kind="blockquote", content=formatted_content)
        expected_block_tag = "md_blockquote"
    else:  # paragraph
        block = Block(kind="paragraph", content=formatted_content)
        expected_block_tag = None  # paragraph uses only base_tag

    render_block(widget, block, base_tag="base")

    rendered_text = _get_text(widget)

    # 1. The rendered text contains the content (without delimiters)
    assert content in rendered_text, (
        f"Expected content '{content}' to appear in rendered text for "
        f"block type '{block_type}', but got: '{rendered_text}'"
    )

    # 2. Find the position of the content and verify tags at that position
    content_idx = _find_text_index(widget, content)
    assert content_idx is not None, (
        f"Could not find content '{content}' in widget text for block type '{block_type}'"
    )

    tags_at_content = _get_tags_at(widget, content_idx)

    # 3. The block-level tag is applied (for non-paragraph blocks)
    if expected_block_tag is not None:
        assert expected_block_tag in tags_at_content, (
            f"Expected block-level tag '{expected_block_tag}' to be applied at "
            f"content position for block type '{block_type}', "
            f"but found tags: {tags_at_content}"
        )

    # 4. The inline formatting tag is also applied to the formatted segment
    assert expected_inline_tag in tags_at_content, (
        f"Expected inline formatting tag '{expected_inline_tag}' to be applied at "
        f"content position for block type '{block_type}', "
        f"but found tags: {tags_at_content}"
    )

    # 5. For paragraph blocks, verify the base tag is applied
    if block_type == "paragraph":
        assert "base" in tags_at_content, (
            f"Expected base tag 'base' to be applied for paragraph block, "
            f"but found tags: {tags_at_content}"
        )
