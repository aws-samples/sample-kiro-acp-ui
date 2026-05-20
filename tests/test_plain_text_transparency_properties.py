"""Property-based tests for plain text transparency.

# Feature: markdown-rendering, Property 11: Plain text transparency

**Validates: Requirements 12.4**
"""

import tkinter as tk

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import render_markdown, setup_tags

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
        # Configure the base tag used in tests
        _widget.tag_configure("base", foreground="#000000")
    return _widget


def _clear_widget(widget):
    """Clear all content from the widget."""
    widget.delete("1.0", tk.END)


def _get_text(widget):
    """Get all text content from widget (strip trailing newline added by tk.Text)."""
    return widget.get("1.0", "end-1c")


def _get_tags_at(widget, index):
    """Get tags applied at a specific index."""
    return widget.tag_names(index)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Plain text that contains NO markdown syntax characters and no newlines.
# Excluded characters: * _ ` # > | - [ ] ( )
# Also exclude newlines to keep it single-line plain text.
# Filter to text where strip() == text (no leading/trailing whitespace)
# because the paragraph parser normalizes whitespace, which is standard
# markdown behavior (trailing spaces in paragraphs are not significant).
plain_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`#>|-[]()\n\r",
        blacklist_categories=("Cs", "Cc"),  # Exclude surrogates and control chars
    ),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip() == s and len(s) > 0)

# Markdown-specific tags that should NOT appear on plain text
MARKDOWN_SPECIFIC_TAGS = {
    "md_bold",
    "md_italic",
    "md_bold_italic",
    "md_inline_code",
    "md_code_block",
    "md_h1",
    "md_h2",
    "md_h3",
    "md_h4",
    "md_h5",
    "md_h6",
    "md_list_1",
    "md_list_2",
    "md_list_3",
    "md_blockquote",
    "md_table",
    "md_table_header",
    "md_link",
    "md_hrule",
}


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(text=plain_text)
def test_plain_text_transparency(text):
    """Property 11: Plain text transparency.

    For any text containing no markdown syntax characters, the renderer SHALL
    produce output identical to plain text insertion — the same text content
    with only the base tag applied.

    # Feature: markdown-rendering, Property 11: Plain text transparency
    """
    widget = _get_widget()
    _clear_widget(widget)

    # Render the plain text through the full public API
    render_markdown(widget, text, base_tag="base")

    # 1. The rendered text content matches the input plus a trailing newline
    #    (the paragraph renderer appends a newline)
    rendered = _get_text(widget)
    expected = text + "\n"
    assert rendered == expected, (
        f"Expected rendered text to be '{expected!r}' but got '{rendered!r}'. "
        f"Plain text should pass through unchanged (with trailing newline from paragraph renderer)."
    )

    # 2. The base tag is applied to the rendered text
    tags_at_start = _get_tags_at(widget, "1.0")
    assert "base" in tags_at_start, (
        f"Expected 'base' tag to be applied at start of text, but found tags: {tags_at_start}"
    )

    # 3. No markdown-specific tags are applied anywhere in the text
    #    Check each character position in the first line
    line_length = len(text)
    for i in range(min(line_length, 20)):  # Check up to 20 chars for performance
        index = f"1.{i}"
        tags = set(_get_tags_at(widget, index))
        applied_md_tags = tags & MARKDOWN_SPECIFIC_TAGS
        assert not applied_md_tags, (
            f"Expected no markdown-specific tags at index {index}, "
            f"but found: {applied_md_tags}. Plain text should only have the base tag."
        )
