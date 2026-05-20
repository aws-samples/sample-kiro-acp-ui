"""Property-based tests for inline link rendering.

# Feature: markdown-rendering, Property 9: Link rendering removes syntax and applies link styling
"""

import tkinter as tk

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import render_inline, setup_tags


def _make_widget():
    """Create a tk.Text widget for testing; skip if display unavailable."""
    try:
        root = tk.Tk()
        root.withdraw()
        text_widget = tk.Text(root)
        setup_tags(text_widget)
        return root, text_widget
    except tk.TclError:
        pytest.skip("Tkinter display not available")


def _get_text(widget):
    """Get all text content from widget (strip trailing newline)."""
    return widget.get("1.0", tk.END).rstrip("\n")


def _get_tags_at(widget, index):
    """Get tags applied at a specific index."""
    return widget.tag_names(index)


# Strategy for link text: non-empty strings without brackets, parens, and markdown delimiters
link_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        whitelist_characters=".,;:!?-+=/&@#%^~",
        blacklist_characters="[](){}*_`\\|<>\n\r",
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

# Strategy for URL: non-empty strings with common URL characters, no closing paren
url_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="/:.-_~?=#&%+@",
        blacklist_characters="()\n\r []{}",
    ),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")


# **Validates: Requirements 10.1**
@settings(max_examples=100, deadline=None)
@given(
    link_text=link_text_strategy,
    url=url_strategy,
)
def test_link_rendering_removes_syntax_and_applies_styling(link_text, url):
    """Property 9: Link rendering removes syntax and applies link styling.

    For any text containing a [text](url) pattern where text and url are
    non-empty, the renderer SHALL display only the link text (not the
    brackets, parentheses, or URL) with underline and link-color styling
    applied (md_link tag).

    # Feature: markdown-rendering, Property 9: Link rendering removes syntax
    # and applies link styling

    **Validates: Requirements 10.1**
    """
    root, w = _make_widget()
    try:
        markdown_input = f"[{link_text}]({url})"
        render_inline(w, markdown_input, ("base_tag",))

        rendered_text = _get_text(w)

        # 1. The rendered text equals just the link text
        assert rendered_text == link_text, (
            f"Expected rendered text to be '{link_text}', got '{rendered_text}'"
        )

        # 2. The md_link tag is applied to the link text
        tags = _get_tags_at(w, "1.0")
        assert "md_link" in tags, f"Expected 'md_link' tag at position 1.0, got tags: {tags}"

        # 3. Brackets, parentheses, and URL are not visible in rendered output
        # The rendered text should be exactly the link text — no extra syntax
        assert "[" not in rendered_text
        assert "]" not in rendered_text
        assert "(" not in rendered_text
        assert ")" not in rendered_text
        # The full markdown syntax should not appear in the output
        assert f"]({url})" not in rendered_text
    finally:
        root.destroy()
