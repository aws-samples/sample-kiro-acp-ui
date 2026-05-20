"""Property-based tests for inline delimiter rendering.

# Feature: markdown-rendering, Property 1: Inline delimiter rendering removes
# delimiters and applies tags

**Validates: Requirements 1.1, 2.1, 3.1**
"""

import tkinter as tk

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import render_inline, setup_tags

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Module-level root window — created once, reused across all test iterations
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
            # Retry once — on macOS the first Tk() call in a process can fail
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

# Text content that does not contain markdown delimiter characters
# Excludes: *, _, `, [, ], (, ), and control characters (which tkinter may strip)
safe_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`[]()\\",
        blacklist_categories=("Cs", "Cc"),  # Exclude surrogates and control chars
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "" and "\n" not in s and "\r" not in s)

# Delimiter types and their expected tags
delimiter_info = st.sampled_from(
    [
        ("**", "**", "md_bold"),
        ("__", "__", "md_bold"),
        ("*", "*", "md_italic"),
        ("_", "_", "md_italic"),
        ("`", "`", "md_inline_code"),
    ]
)


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    content=safe_text,
    delim_data=delimiter_info,
)
def test_inline_delimiter_rendering_removes_delimiters_and_applies_tags(content, delim_data):
    """Property 1: Inline delimiter rendering removes delimiters and applies tags.

    For any non-empty text string that does not itself contain markdown delimiter
    characters, wrapping it in valid inline delimiters (**...**, __...__, *...*,
    _..._, or `...`) and rendering it SHALL produce output where the delimiter
    characters are absent from the displayed text and the appropriate formatting
    tag is applied.

    # Feature: markdown-rendering, Property 1: Inline delimiter rendering
    # removes delimiters and applies tags
    """
    open_delim, close_delim, expected_tag = delim_data

    # Construct the markdown text with delimiters wrapping the content
    markdown_text = f"{open_delim}{content}{close_delim}"

    # Get or create the widget (skip if no display)
    widget = _get_widget()
    _clear_widget(widget)

    render_inline(widget, markdown_text, ())

    # 1. The rendered text in the widget equals the content without delimiters
    rendered_text = _get_text(widget)
    assert rendered_text == content, (
        f"Expected rendered text to be '{content}' but got '{rendered_text}'. "
        f"Delimiters '{open_delim}...{close_delim}' should be removed."
    )

    # 2. The appropriate tag is applied
    tags = _get_tags_at(widget, "1.0")
    assert expected_tag in tags, (
        f"Expected tag '{expected_tag}' to be applied for delimiter "
        f"'{open_delim}...{close_delim}', but found tags: {tags}"
    )
