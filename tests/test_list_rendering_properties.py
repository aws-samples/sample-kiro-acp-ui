"""Property-based tests for list rendering.

# Feature: markdown-rendering, Property 6: List items render with markers and indentation

**Validates: Requirements 6.1, 7.1**
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

# List item text: non-empty, no newlines, no markdown delimiters
list_item_text = st.text(
    alphabet=st.characters(
        blacklist_characters="*_`[]()\\#>|-+\n\r",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# List type: unordered or ordered
list_type = st.sampled_from(["ulist", "olist"])

# Indent level: 1, 2, or 3 (corresponding to 0, 3, 6 spaces in raw markdown)
indent_level = st.sampled_from([1, 2, 3])


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(
    item_text=list_item_text,
    kind=list_type,
    level=indent_level,
)
def test_list_items_render_with_markers_and_indentation(item_text, kind, level):
    """Property 6: List items render with markers and indentation.

    For any line beginning with a valid unordered list marker (- , * , + )
    or ordered list marker (\\d+. ), optionally preceded by spaces, the renderer
    SHALL display the line with appropriate indentation proportional to nesting
    level, preserving the bullet/number marker in the output while omitting the
    raw markdown prefix spacing.

    # Feature: markdown-rendering, Property 6: List items render with markers and indentation
    """
    widget = _get_widget()
    _clear_widget(widget)

    # Create a Block representing a single list item at the given level
    block = Block(kind=kind, content=item_text, level=level, meta={"levels": [level]})
    render_block(widget, block, base_tag="base")

    rendered_text = _get_text(widget)

    # 1. For unordered lists: the rendered output contains a bullet character
    #    followed by the item text
    if kind == "ulist":
        assert "\u2022 " in rendered_text, (
            f"Expected bullet character '\u2022 ' in rendered output for unordered list, "
            f"got: '{rendered_text}'"
        )
        assert item_text in rendered_text, (
            f"Expected item text '{item_text}' in rendered output, got: '{rendered_text}'"
        )

    # 2. For ordered lists: the rendered output contains a number followed by
    #    ". " and the item text
    if kind == "olist":
        assert "1. " in rendered_text, (
            f"Expected '1. ' in rendered output for ordered list, got: '{rendered_text}'"
        )
        assert item_text in rendered_text, (
            f"Expected item text '{item_text}' in rendered output, got: '{rendered_text}'"
        )

    # 3. The appropriate md_list_{level} tag is applied
    expected_tag = f"md_list_{level}"
    tags = _get_tags_at(widget, "1.0")
    assert expected_tag in tags, (
        f"Expected tag '{expected_tag}' to be applied for list level {level}, "
        f"but found tags: {tags}"
    )

    # 4. The raw markdown prefix (- , * , + , 1. ) is not visible in the output
    #    (the raw markdown markers are stripped by the parser before reaching
    #    render_block, so the content should not contain them).
    #    We verify that no raw unordered markers appear as prefix in the output.
    if kind == "ulist":
        # The output should use bullet char, not raw markdown markers
        assert not rendered_text.startswith("- "), (
            "Raw markdown prefix '- ' should not appear in rendered output"
        )
        assert not rendered_text.startswith("* "), (
            "Raw markdown prefix '* ' should not appear in rendered output"
        )
        assert not rendered_text.startswith("+ "), (
            "Raw markdown prefix '+ ' should not appear in rendered output"
        )
    if kind == "olist":
        # The output should use sequential numbering from render_block,
        # not the raw markdown "1. " prefix from the source
        # (render_block generates "1. " for the first item which is correct
        # rendered output, distinct from the raw markdown prefix)
        pass
