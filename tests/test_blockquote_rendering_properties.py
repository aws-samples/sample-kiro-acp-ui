"""Property-based tests for blockquote rendering.

# Feature: markdown-rendering, Property 7: Blockquote rendering removes prefix and applies styling

**Validates: Requirements 8.1**
"""

import tkinter as tk

import pytest
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


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Blockquote text content: non-empty, no newlines, no markdown delimiters
# that would confuse parsing
blockquote_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`[]()\\>#\n\r",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip() != "")


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(content=blockquote_text)
def test_blockquote_rendering_removes_prefix_and_applies_styling(content):
    """Property 7: Blockquote rendering removes prefix and applies styling.

    For any line beginning with `> `, the renderer SHALL display the line
    content without the `> ` prefix, with blockquote indentation and distinct
    foreground color applied (md_blockquote tag).

    Note: render_block() receives a Block of kind "blockquote" where the
    content already has the `> ` prefix stripped by parse_blocks().

    # Feature: markdown-rendering, Property 7: Blockquote rendering removes
    # prefix and applies styling

    **Validates: Requirements 8.1**
    """
    widget = _get_widget()
    _clear_widget(widget)

    # Create a blockquote block (parse_blocks strips the `> ` prefix,
    # so content is already without the prefix)
    block = Block(kind="blockquote", content=content)
    render_block(widget, block, base_tag="base")

    rendered_text = _get_text(widget)

    # 1. The rendered text contains the content without the `> ` prefix
    assert content in rendered_text, (
        f"Expected blockquote content '{content}' to appear in rendered text, "
        f"but got '{rendered_text}'"
    )

    # 2. The `md_blockquote` tag is applied to the rendered text
    tags = _get_tags_at(widget, "1.0")
    assert "md_blockquote" in tags, (
        f"Expected 'md_blockquote' tag to be applied, but found tags: {tags}"
    )

    # 3. The `> ` prefix is not visible in the rendered output
    assert not rendered_text.startswith("> "), (
        f"The '> ' prefix should not be visible in rendered output, but got '{rendered_text}'"
    )
