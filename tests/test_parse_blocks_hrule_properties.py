"""Property-based tests for block parser — horizontal rules.

# Feature: markdown-rendering, Property 8: Horizontal rule detection and rendering
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import parse_blocks


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The three valid horizontal rule characters
hrule_chars = st.sampled_from(["-", "*", "_"])

# Count of rule characters (3 or more, up to 20)
hrule_count = st.integers(min_value=3, max_value=20)

# Whether to insert spaces between characters
use_spaces = st.booleans()


@st.composite
def hrule_line(draw):
    """Generate a valid horizontal rule line.

    Produces a line consisting solely of 3+ of the same character
    (one of -, *, _), optionally separated by spaces.
    """
    char = draw(hrule_chars)
    count = draw(hrule_count)
    spaces = draw(use_spaces)

    if spaces:
        # Insert spaces between characters
        return (" ".join([char] * count))
    else:
        return char * count


@st.composite
def hrule_line_with_leading_spaces(draw):
    """Generate a valid horizontal rule line with optional leading spaces (0-3)."""
    line = draw(hrule_line())
    leading = draw(st.integers(min_value=0, max_value=3))
    return " " * leading + line


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


# **Validates: Requirements 9.1**
@settings(max_examples=100)
@given(line=hrule_line_with_leading_spaces())
def test_valid_hrule_produces_hrule_block(line):
    """Property 8: Horizontal rule detection and rendering.

    For any line consisting solely of three or more `-`, `*`, or `_`
    characters (optionally separated by spaces), `parse_blocks()` SHALL
    produce a Block with kind="hrule".

    # Feature: markdown-rendering, Property 8: Horizontal rule detection and rendering
    """
    blocks = parse_blocks(line)
    assert len(blocks) == 1, f"Expected 1 block, got {len(blocks)} for input: {line!r}"
    assert blocks[0].kind == "hrule", (
        f"Expected kind='hrule', got kind='{blocks[0].kind}' for input: {line!r}"
    )


# **Validates: Requirements 9.1**
@settings(max_examples=100)
@given(line=hrule_line())
def test_hrule_with_spaces_between_chars_produces_hrule(line):
    """Property 8 (spaces variant): Lines with spaces between rule characters
    still produce hrule blocks.

    # Feature: markdown-rendering, Property 8: Horizontal rule detection and rendering
    """
    blocks = parse_blocks(line)
    assert len(blocks) == 1
    assert blocks[0].kind == "hrule", (
        f"Expected kind='hrule', got kind='{blocks[0].kind}' for input: {line!r}"
    )


# **Validates: Requirements 9.1**
@settings(max_examples=100)
@given(
    char=hrule_chars,
    count=st.integers(min_value=1, max_value=2),
)
def test_fewer_than_three_chars_not_hrule(char, count):
    """Property 8 (negative): Lines with fewer than 3 rule characters do NOT
    produce hrule blocks.

    # Feature: markdown-rendering, Property 8: Horizontal rule detection and rendering
    """
    line = char * count
    blocks = parse_blocks(line)
    # Should not be an hrule
    for block in blocks:
        assert block.kind != "hrule", (
            f"Expected non-hrule for input: {line!r}, got kind='hrule'"
        )


# **Validates: Requirements 9.1**
@settings(max_examples=100)
@given(
    chars=st.lists(
        hrule_chars,
        min_size=3,
        max_size=10,
    ).filter(lambda cs: len(set(cs)) > 1),  # Ensure mixed characters
)
def test_mixed_chars_not_hrule(chars):
    """Property 8 (negative): Lines with mixed rule characters (e.g., `-*_`)
    do NOT produce hrule blocks.

    # Feature: markdown-rendering, Property 8: Horizontal rule detection and rendering
    """
    line = "".join(chars)
    blocks = parse_blocks(line)
    # Mixed characters should not produce an hrule
    for block in blocks:
        assert block.kind != "hrule", (
            f"Expected non-hrule for mixed input: {line!r}, got kind='hrule'"
        )
