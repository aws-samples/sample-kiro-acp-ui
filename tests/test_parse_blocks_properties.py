"""Property-based tests for parse_blocks() function.

**Feature: markdown-rendering, Property 4: Fenced code block rendering preserves content and removes fences**
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import parse_blocks


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate content lines that don't contain triple backticks
_content_line = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),  # Exclude surrogates
        blacklist_characters="\r",
    ),
    min_size=0,
    max_size=80,
).filter(lambda s: "```" not in s)

# Generate optional language identifiers (alphanumeric strings)
_lang_identifier = st.one_of(
    st.just(""),
    st.from_regex(r"[a-zA-Z][a-zA-Z0-9]*", fullmatch=True).filter(lambda s: len(s) <= 20),
)


# ---------------------------------------------------------------------------
# Property 4: Fenced code block rendering preserves content and removes fences
# **Validates: Requirements 4.1, 4.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    content_lines=st.lists(_content_line, min_size=0, max_size=10),
    lang=_lang_identifier,
)
def test_fenced_code_block_preserves_content_and_removes_fences(content_lines, lang):
    """Property 4: Fenced code block rendering preserves content and removes fences.

    For any multi-line text wrapped in triple-backtick fences (with or without
    a language identifier), parse_blocks() SHALL produce a Block with kind="code",
    the content between fences preserved exactly, fence lines and language
    identifier omitted from content, and meta containing the language if specified.

    **Validates: Requirements 4.1, 4.2**
    """
    # Build the fenced code block markdown
    opening_fence = "```" + lang
    closing_fence = "```"
    expected_content = "\n".join(content_lines)

    # Assemble the full markdown input
    lines = [opening_fence] + content_lines + [closing_fence]
    markdown_input = "\n".join(lines)

    # Parse
    blocks = parse_blocks(markdown_input)

    # 1. parse_blocks returns exactly one block of kind "code"
    assert len(blocks) == 1, (
        f"Expected exactly 1 block, got {len(blocks)}: {blocks}"
    )
    block = blocks[0]
    assert block.kind == "code", (
        f"Expected block kind 'code', got '{block.kind}'"
    )

    # 2. The content field matches the original content between fences
    assert block.content == expected_content, (
        f"Content mismatch.\nExpected: {expected_content!r}\nGot: {block.content!r}"
    )

    # 3. The language identifier is in meta["lang"] when present
    if lang:
        assert "lang" in block.meta, (
            f"Expected 'lang' in meta when language is '{lang}', got {block.meta}"
        )
        assert block.meta["lang"] == lang, (
            f"Expected meta['lang'] == '{lang}', got '{block.meta['lang']}'"
        )
    else:
        assert block.meta == {}, (
            f"Expected empty meta when no language specified, got {block.meta}"
        )

    # 4. Fence lines are not in the content
    assert opening_fence not in block.content or opening_fence == expected_content or opening_fence in expected_content, (
        "Opening fence should not appear in content unless it was part of the original content lines"
    )
    # More precise check: the content should be exactly the joined content_lines
    # (already verified in assertion 2), which means fences are excluded
