"""Property-based test for inline parser — unmatched delimiters.

# Feature: markdown-rendering, Property 2: Unmatched delimiters are displayed verbatim

**Validates: Requirements 1.3, 2.2, 3.2**
"""

import tkinter as tk

import pytest
from hypothesis import assume, given, settings
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


# Strategy: opening delimiters that can be unmatched
_DELIMITERS = ["**", "__", "*", "_", "`"]
delimiter_strategy = st.sampled_from(_DELIMITERS)

# Strategy: text content that does not contain any markdown delimiter characters.
# This ensures the only delimiter in the input is the one we prepend.
# Also excludes null characters (tkinter Text widget strips them) and
# newlines (property is about single-line unmatched delimiters).
safe_text_strategy = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`\n\r\x00",
        blacklist_categories=("Cs",),  # Exclude surrogates
    ),
    min_size=1,
    max_size=50,
)


# **Validates: Requirements 1.3, 2.2, 3.2**
@settings(max_examples=100)
@given(
    delimiter=delimiter_strategy,
    text_content=safe_text_strategy,
)
def test_unmatched_delimiters_displayed_verbatim(delimiter, text_content):
    """Property 2: Unmatched delimiters are displayed verbatim.

    For any text containing an opening inline delimiter (**, __, *, _, or `)
    without a corresponding closing delimiter on the same line, the renderer
    SHALL display the text verbatim including the delimiter characters, with
    no formatting tags applied to the delimiter.

    # Feature: markdown-rendering, Property 2: Unmatched delimiters are displayed verbatim
    """
    # Ensure text_content doesn't accidentally form a closing delimiter
    # by not containing the delimiter substring itself
    assume(delimiter not in text_content)

    # Construct input: delimiter + text (no closing delimiter)
    input_text = delimiter + text_content

    root, w = _make_widget()
    try:
        base_tags = ("base_tag",)
        render_inline(w, input_text, base_tags)

        # 1. The rendered text equals the full input (displayed verbatim)
        rendered_text = w.get("1.0", tk.END).rstrip("\n")
        assert rendered_text == input_text, (
            f"Expected verbatim text '{input_text}', got '{rendered_text}'"
        )

        # 2. No formatting tags (md_bold, md_italic, md_inline_code) are applied
        formatting_tags = {"md_bold", "md_italic", "md_inline_code"}
        # Check all character positions in the rendered text
        for i in range(len(rendered_text)):
            index = f"1.{i}"
            tags_at_pos = set(w.tag_names(index))
            applied_formatting = tags_at_pos & formatting_tags
            assert not applied_formatting, (
                f"Formatting tags {applied_formatting} found at position {i} "
                f"for unmatched delimiter input '{input_text}'"
            )
    finally:
        root.destroy()
