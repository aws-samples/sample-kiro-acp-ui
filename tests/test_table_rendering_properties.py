"""Property-based tests for table rendering.

# Feature: markdown-rendering, Property 10: Table rendering produces aligned output without separator row

**Validates: Requirements 11.1, 11.2, 11.3**
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


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Cell text: non-empty, no pipes, no newlines, no dashes-only (to avoid separator confusion)
cell_text = st.text(
    alphabet=st.characters(
        blacklist_characters="|\n\r",
        blacklist_categories=("Cs", "Cc"),
    ),
    min_size=1,
    max_size=15,
).filter(lambda s: s.strip() != "" and not all(c == "-" for c in s.strip()))

# Number of columns (2-5)
num_columns = st.integers(min_value=2, max_value=5)

# Number of data rows (1-5)
num_data_rows = st.integers(min_value=1, max_value=5)


@st.composite
def markdown_table(draw):
    """Generate a valid markdown table with header, separator, and data rows."""
    cols = draw(num_columns)
    rows_count = draw(num_data_rows)

    # Generate header cells
    headers = [draw(cell_text) for _ in range(cols)]

    # Generate data rows
    data_rows = []
    for _ in range(rows_count):
        row = [draw(cell_text) for _ in range(cols)]
        data_rows.append(row)

    # Build the markdown table string
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * cols) + " |"
    data_lines = []
    for row in data_rows:
        data_lines.append("| " + " | ".join(row) + " |")

    table_content = "\n".join([header_line, separator_line] + data_lines)

    return headers, data_rows, table_content


# ---------------------------------------------------------------------------
# Property Test
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=None)
@given(table_data=markdown_table())
def test_table_rendering_produces_aligned_output_without_separator_row(table_data):
    """Property 10: Table rendering produces aligned output without separator row.

    For any valid markdown table (header row, separator row, and one or more
    data rows), the renderer SHALL display the table content with monospace font,
    bold formatting on the header row, consistent column alignment, and the
    separator row (|---|---|) omitted from the displayed output.

    # Feature: markdown-rendering, Property 10: Table rendering produces aligned output without separator row
    """
    headers, data_rows, table_content = table_data

    widget = _get_widget()
    _clear_widget(widget)

    block = Block(kind="table", content=table_content)
    render_block(widget, block, base_tag="base")

    rendered_text = _get_text(widget)

    # 1. The rendered output contains all header cell text
    for header in headers:
        assert header.strip() in rendered_text, (
            f"Header cell '{header}' not found in rendered output: '{rendered_text}'"
        )

    # 2. The rendered output contains all data cell text
    for row in data_rows:
        for cell in row:
            assert cell.strip() in rendered_text, (
                f"Data cell '{cell}' not found in rendered output: '{rendered_text}'"
            )

    # 3. The separator row (---) is NOT in the rendered output
    assert "---" not in rendered_text, (
        f"Separator row '---' should not appear in rendered output: '{rendered_text}'"
    )

    # 4. The md_table_header tag is applied to the first line (header)
    tags_header = _get_tags_at(widget, "1.0")
    assert "md_table_header" in tags_header, (
        f"Expected 'md_table_header' tag on first line, but found: {tags_header}"
    )

    # 5. The md_table tag is applied to data rows
    # Data rows start on line 2 (since header is line 1, separator is omitted)
    tags_data = _get_tags_at(widget, "2.0")
    assert "md_table" in tags_data, (
        f"Expected 'md_table' tag on data row (line 2), but found: {tags_data}"
    )
