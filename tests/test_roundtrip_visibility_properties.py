"""Property-based tests for round-trip visibility.

# Feature: markdown-rendering, Property 12: Round-trip visibility — no raw delimiters in rendered output

**Validates: Requirements 13.4**
"""

import pytest
import tkinter as tk

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
    return _widget


def _clear_widget(widget):
    """Clear all content from the widget."""
    widget.delete("1.0", tk.END)


def _get_text(widget):
    """Get all text content from widget (strip trailing newline)."""
    return widget.get("1.0", tk.END).rstrip("\n")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Text content that does not contain markdown delimiter characters or newlines
_safe_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`#[]()\\|>+-\n\r",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")


# Strategy: generate valid markdown with properly matched delimiters
# Each generated value is a single-line input with one formatting type applied
@st.composite
def valid_markdown_text(draw):
    """Generate valid markdown text with properly matched delimiters.

    Generates text content and randomly wraps it in one of:
    - **...** (bold)
    - *...* (italic)
    - `...` (inline code)
    - # prefix (header)
    - plain text (no formatting)
    """
    content = draw(_safe_text)
    formatting = draw(st.sampled_from([
        "bold_asterisk",
        "italic_asterisk",
        "inline_code",
        "header",
        "plain",
    ]))

    if formatting == "bold_asterisk":
        return f"**{content}**"
    elif formatting == "italic_asterisk":
        return f"*{content}*"
    elif formatting == "inline_code":
        return f"`{content}`"
    elif formatting == "header":
        level = draw(st.integers(min_value=1, max_value=6))
        return f"{'#' * level} {content}"
    else:
        return content


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(markdown_input=valid_markdown_text())
def test_roundtrip_visibility_no_raw_delimiters_in_rendered_output(markdown_input):
    """Property 12: Round-trip visibility — no raw delimiters in rendered output.

    For any valid markdown text (where all delimiters are properly matched),
    the rendered output SHALL contain no visible raw markdown delimiter characters
    (**,  __, `, ```, # at line start) except within code block content.

    # Feature: markdown-rendering, Property 12: Round-trip visibility — no raw delimiters in rendered output
    """
    widget = _get_widget()
    _clear_widget(widget)

    render_markdown(widget, markdown_input)

    rendered_text = _get_text(widget)

    # 1. The rendered output does NOT contain ** (bold delimiter)
    assert "**" not in rendered_text, (
        f"Rendered output contains raw '**' delimiter.\n"
        f"Input: {markdown_input!r}\n"
        f"Output: {rendered_text!r}"
    )

    # 2. The rendered output does NOT contain __ (bold delimiter)
    assert "__" not in rendered_text, (
        f"Rendered output contains raw '__' delimiter.\n"
        f"Input: {markdown_input!r}\n"
        f"Output: {rendered_text!r}"
    )

    # 3. The rendered output does NOT contain unmatched backticks
    #    (since we generate properly matched backtick pairs, no backticks
    #    should remain in the output)
    assert "`" not in rendered_text, (
        f"Rendered output contains raw backtick delimiter.\n"
        f"Input: {markdown_input!r}\n"
        f"Output: {rendered_text!r}"
    )

    # 4. The rendered output does NOT start with '# ' (headers have # removed)
    #    Check that no line in the output starts with a # prefix
    for line in rendered_text.split("\n"):
        assert not line.startswith("# "), (
            f"Rendered output line starts with raw '# ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
        assert not line.startswith("## "), (
            f"Rendered output line starts with raw '## ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
        assert not line.startswith("### "), (
            f"Rendered output line starts with raw '### ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
        assert not line.startswith("#### "), (
            f"Rendered output line starts with raw '#### ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
        assert not line.startswith("##### "), (
            f"Rendered output line starts with raw '##### ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
        assert not line.startswith("###### "), (
            f"Rendered output line starts with raw '###### ' header prefix.\n"
            f"Input: {markdown_input!r}\n"
            f"Output line: {line!r}"
        )
