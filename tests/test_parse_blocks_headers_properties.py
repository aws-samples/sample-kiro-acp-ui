"""Property-based tests for block parser — headers.

# Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import Block, parse_blocks


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Header levels: integers 1-6
header_levels = st.integers(min_value=1, max_value=6)

# Header text content: non-empty text without newlines, not starting with #
header_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\n\r",
    ),
    min_size=1,
    max_size=80,
).filter(lambda t: not t.startswith("#") and t.strip() == t and len(t.strip()) > 0)

# Non-header lines: text with # mid-line (not at start)
midline_hash_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="\n\r|",
    ),
    min_size=1,
    max_size=40,
).map(lambda t: t.rstrip()).filter(lambda t: len(t) > 0 and not t.startswith("#") and not t.startswith("> ") and not t.startswith("- ") and not t.startswith("* ") and not t.startswith("+ "))

# Too many hashes: 7+ # characters
too_many_hashes_level = st.integers(min_value=7, max_value=12)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


# **Validates: Requirements 5.1, 5.2, 5.3**
@settings(max_examples=100)
@given(level=header_levels, text=header_text)
def test_valid_headers_produce_header_blocks_with_correct_level(level, text):
    """Property 5.1: Valid headers produce blocks with kind='header' and correct level.

    For any line beginning with 1-6 # characters followed by a space,
    parse_blocks() SHALL produce a Block with kind="header" and level
    equal to the number of # characters.

    # Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
    """
    markdown_line = "#" * level + " " + text
    blocks = parse_blocks(markdown_line)

    assert len(blocks) == 1
    assert blocks[0].kind == "header"
    assert blocks[0].level == level


# **Validates: Requirements 5.1, 5.2, 5.3**
@settings(max_examples=100)
@given(level=header_levels, text=header_text)
def test_valid_headers_content_does_not_contain_hash_prefix(level, text):
    """Property 5.2: Content field does not contain the # prefix.

    For any valid header line, the content field of the resulting Block
    SHALL contain the text without the leading # characters and space.

    # Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
    """
    markdown_line = "#" * level + " " + text
    blocks = parse_blocks(markdown_line)

    assert len(blocks) == 1
    block = blocks[0]
    # Content should be the text after "# " prefix
    assert block.content == text
    # Content should NOT start with #
    assert not block.content.startswith("#")


# **Validates: Requirements 5.1, 5.2, 5.3**
@settings(max_examples=100)
@given(prefix=midline_hash_text)
def test_hash_midline_produces_paragraph_block(prefix):
    """Property 5.3: Lines with # mid-line produce paragraph blocks.

    For any line where # appears mid-line (not at the start), parse_blocks()
    SHALL produce a paragraph block, not a header block.

    # Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
    """
    # Create a line with # somewhere in the middle
    line = prefix + " # something"
    blocks = parse_blocks(line)

    assert len(blocks) >= 1
    # The block should NOT be a header
    assert blocks[0].kind != "header"


# **Validates: Requirements 5.1, 5.2, 5.3**
@settings(max_examples=100)
@given(level=header_levels, text=header_text)
def test_hash_without_trailing_space_produces_paragraph(level, text):
    """Property 5.4: Lines with # without trailing space produce paragraph blocks.

    For any line starting with # characters but NOT followed by a space,
    parse_blocks() SHALL produce a paragraph block.

    # Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
    """
    # No space between hashes and text — must not start with space
    assume(not text.startswith(" "))
    markdown_line = "#" * level + text  # No space after #
    blocks = parse_blocks(markdown_line)

    assert len(blocks) >= 1
    # Should NOT be parsed as a header
    assert blocks[0].kind != "header"


# **Validates: Requirements 5.1, 5.2, 5.3**
@settings(max_examples=100)
@given(level=too_many_hashes_level, text=header_text)
def test_seven_plus_hashes_produces_paragraph(level, text):
    """Property 5.5: 7+ # characters produce paragraph blocks.

    For any line beginning with 7 or more # characters (even followed by
    a space), parse_blocks() SHALL produce a paragraph block, not a header.

    # Feature: markdown-rendering, Property 5: Header rendering removes # prefix and applies level-appropriate tag
    """
    markdown_line = "#" * level + " " + text
    blocks = parse_blocks(markdown_line)

    assert len(blocks) >= 1
    # Should NOT be parsed as a header since only 1-6 # are valid
    assert blocks[0].kind != "header"
