"""Markdown renderer for tkinter Text widgets.

This module parses markdown text and inserts formatted content into a tkinter
tk.Text widget using tags. It supports block-level elements (headers, code blocks,
lists, blockquotes, tables, horizontal rules) and inline formatting (bold, italic,
inline code, links).

The renderer uses a regex-based, two-pass parsing approach:
1. Block-level pass: splits text into block elements
2. Inline pass: within each block, parses inline formatting

Only Python standard library modules are used (no external dependencies).
"""

from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tag definitions
# ---------------------------------------------------------------------------

MARKDOWN_TAGS: dict[str, dict] = {
    # Headers
    "md_h1": {"font": ("TkDefaultFont", 18, "bold"), "spacing1": 8, "spacing3": 4},
    "md_h2": {"font": ("TkDefaultFont", 16, "bold"), "spacing1": 6, "spacing3": 3},
    "md_h3": {"font": ("TkDefaultFont", 14, "bold"), "spacing1": 4, "spacing3": 2},
    "md_h4": {"font": ("TkDefaultFont", 12, "bold"), "spacing1": 3, "spacing3": 2},
    "md_h5": {"font": ("TkDefaultFont", 11, "bold"), "spacing1": 2, "spacing3": 1},
    "md_h6": {"font": ("TkDefaultFont", 10, "bold"), "spacing1": 2, "spacing3": 1},
    # Inline formatting
    "md_bold": {"font": ("TkDefaultFont", 10, "bold")},
    "md_italic": {"font": ("TkDefaultFont", 10, "italic")},
    "md_bold_italic": {"font": ("TkDefaultFont", 10, "bold italic")},
    "md_inline_code": {"font": ("Courier", 10), "background": "#f0f0f0"},
    # Code blocks
    "md_code_block": {
        "font": ("Courier", 10),
        "background": "#f5f5f5",
        "lmargin1": 20,
        "lmargin2": 20,
    },
    # Lists
    "md_list_1": {"lmargin1": 20, "lmargin2": 30},
    "md_list_2": {"lmargin1": 40, "lmargin2": 50},
    "md_list_3": {"lmargin1": 60, "lmargin2": 70},
    # Blockquote
    "md_blockquote": {"lmargin1": 20, "lmargin2": 20, "foreground": "#555555"},
    # Table
    "md_table": {"font": ("Courier", 10)},
    "md_table_header": {"font": ("Courier", 10, "bold")},
    # Link
    "md_link": {"foreground": "#1a73e8", "underline": True},
    # Horizontal rule
    "md_hrule": {"foreground": "#cccccc"},
}


# ---------------------------------------------------------------------------
# Link counter for unique tag names
# ---------------------------------------------------------------------------

_link_counter: int = 0


def _is_valid_url(url: str) -> bool:
    """Check if a URL is valid for click handling.

    Valid URLs must be non-empty and start with http://, https://, ftp://, or mailto:.
    """
    if not url or not url.strip():
        return False
    url_lower = url.strip().lower()
    return url_lower.startswith(("http://", "https://", "ftp://", "mailto:"))


# ---------------------------------------------------------------------------
# Tag setup
# ---------------------------------------------------------------------------


def setup_tags(text_widget: tk.Text) -> None:
    """Configure all markdown-related tags on the text widget.

    This should be called once during widget initialization to register
    all markdown-specific tags that the renderer will use.

    Args:
        text_widget: The tk.Text widget to configure tags on.
    """
    for tag_name, config in MARKDOWN_TAGS.items():
        text_widget.tag_configure(tag_name, **config)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """Represents a parsed block-level element.

    Attributes:
        kind: The type of block element. One of: "header", "code", "ulist",
              "olist", "blockquote", "hrule", "table", "paragraph".
        content: The raw content of the block.
        level: Context-dependent level value. Header level (1-6), list indent
               level, or 0 for blocks without a level concept.
        meta: Additional metadata (e.g., language for code blocks).
    """

    kind: str
    content: str
    level: int = 0
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Block-level patterns
# ---------------------------------------------------------------------------

_RE_FENCE = re.compile(r"^(`{3,})(.*)")
_RE_HEADER = re.compile(r"^(#{1,6}) (.+)")
_RE_HRULE = re.compile(r"^[ ]{0,3}([-*_])(?:\s*\1){2,}\s*$")
_RE_ULIST = re.compile(r"^( *)[-*+] (.+)")
_RE_OLIST = re.compile(r"^( *)\d+\. (.+)")
_RE_BLOCKQUOTE = re.compile(r"^> ?(.*)")


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------


def _indent_level(spaces: str) -> int:
    """Calculate list indent level from leading spaces.

    0-2 spaces = level 1, 3-5 = level 2, 6+ = level 3 (capped).
    """
    n = len(spaces)
    if n <= 2:
        return 1
    if n <= 5:
        return 2
    return 3


def parse_blocks(content: str) -> list[Block]:
    """Split markdown text into block-level elements.

    Uses a line-by-line state machine with two states: ``normal`` and
    ``in_code_block``. Consecutive lines of the same groupable type
    (list items, table rows, blockquote lines) are merged into a single
    Block.

    Args:
        content: The raw markdown string to parse.

    Returns:
        A list of Block instances representing the parsed structure.
    """
    if not content:
        return []

    blocks: list[Block] = []
    lines = content.split("\n")

    state = "normal"
    code_lines: list[str] = []
    code_lang = ""
    code_fence_len = 0

    for line in lines:
        if state == "in_code_block":
            # Check for closing fence (must be at least as many backticks)
            fence_match = _RE_FENCE.match(line)
            if fence_match and len(fence_match.group(1)) >= code_fence_len and fence_match.group(2).strip() == "":
                # Closing fence found
                blocks.append(Block(
                    kind="code",
                    content="\n".join(code_lines),
                    meta={"lang": code_lang} if code_lang else {},
                ))
                code_lines = []
                code_lang = ""
                code_fence_len = 0
                state = "normal"
            else:
                code_lines.append(line)
            continue

        # --- normal state ---

        # 1. Fenced code block opening
        fence_match = _RE_FENCE.match(line)
        if fence_match:
            code_fence_len = len(fence_match.group(1))
            code_lang = fence_match.group(2).strip()
            state = "in_code_block"
            continue

        # 2. Header
        header_match = _RE_HEADER.match(line)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2)
            blocks.append(Block(kind="header", content=text, level=level))
            continue

        # 3. Horizontal rule
        if _RE_HRULE.match(line):
            blocks.append(Block(kind="hrule", content=""))
            continue

        # 4. Unordered list item
        ulist_match = _RE_ULIST.match(line)
        if ulist_match:
            indent = ulist_match.group(1)
            text = ulist_match.group(2)
            level = _indent_level(indent)
            # Group with previous ulist block if same kind
            if blocks and blocks[-1].kind == "ulist":
                blocks[-1].content += "\n" + text
                # Keep the level of the first item (or update — design says
                # each item can have its own level, but content is grouped).
                # Store per-item levels in meta for rendering.
                blocks[-1].meta.setdefault("levels", []).append(level)
            else:
                blocks.append(Block(
                    kind="ulist", content=text, level=level,
                    meta={"levels": [level]},
                ))
            continue

        # 5. Ordered list item
        olist_match = _RE_OLIST.match(line)
        if olist_match:
            indent = olist_match.group(1)
            text = olist_match.group(2)
            level = _indent_level(indent)
            if blocks and blocks[-1].kind == "olist":
                blocks[-1].content += "\n" + text
                blocks[-1].meta.setdefault("levels", []).append(level)
            else:
                blocks.append(Block(
                    kind="olist", content=text, level=level,
                    meta={"levels": [level]},
                ))
            continue

        # 6. Blockquote
        bq_match = _RE_BLOCKQUOTE.match(line)
        if bq_match:
            text = bq_match.group(1)
            if blocks and blocks[-1].kind == "blockquote":
                blocks[-1].content += "\n" + text
            else:
                blocks.append(Block(kind="blockquote", content=text))
            continue

        # 7. Table row (contains |)
        if "|" in line:
            if blocks and blocks[-1].kind == "table":
                blocks[-1].content += "\n" + line
            else:
                blocks.append(Block(kind="table", content=line))
            continue

        # 8. Default: paragraph
        stripped = line.strip()
        if not stripped:
            # Empty line — break paragraph grouping
            # We use a sentinel to prevent the next line from merging
            # with the previous paragraph block.
            blocks.append(Block(kind="_empty", content=""))
            continue
        if blocks and blocks[-1].kind == "paragraph":
            blocks[-1].content += "\n" + stripped
        else:
            blocks.append(Block(kind="paragraph", content=stripped))

    # Handle unclosed code block (Req 4.3)
    if state == "in_code_block":
        blocks.append(Block(
            kind="code",
            content="\n".join(code_lines),
            meta={"lang": code_lang} if code_lang else {},
        ))

    # Remove empty sentinel blocks used for paragraph separation
    return [b for b in blocks if b.kind != "_empty"]


# ---------------------------------------------------------------------------
# Inline parsing
# ---------------------------------------------------------------------------

# Regex patterns for inline formatting (compiled for performance)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*")
_RE_BOLD_ASTERISK = re.compile(r"\*\*(.+?)\*\*")
_RE_BOLD_UNDERSCORE = re.compile(r"__(.+?)__")
# Italic patterns use lookbehind/lookahead to avoid matching * that is part of **
_RE_ITALIC_ASTERISK = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_ITALIC_UNDERSCORE = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")


def render_inline(text_widget: tk.Text, text: str, tags: tuple[str, ...]) -> None:
    """Parse and render inline formatting within a text segment.

    Uses a segment-based approach: finds all inline formatting patterns,
    splits text into segments (formatted and plain), then inserts each
    segment with appropriate tags.

    Processing order (priority):
    1. Inline code (`` `...` ``) — protects content from further parsing
    2. Links [text](url)
    3. Bold+italic ***text***
    4. Bold **text** / __text__
    5. Italic *text* / _text_

    Unmatched delimiters (no closing delimiter on same line) are displayed
    verbatim including the delimiter characters.

    Args:
        text_widget: The tk.Text widget to insert content into.
        text: The text to parse for inline formatting.
        tags: Tuple of tag names to apply as base tags (e.g., block-level
              tag + base_tag).
    """
    if not text:
        return

    # Build a list of segments: (start, end, content, extra_tags, is_link, url)
    # Each segment represents a formatted region that should not be further parsed.
    segments: list[tuple[int, int, str, tuple[str, ...], str | None]] = []

    # 1. Inline code — highest priority, protects content from further parsing
    for match in _RE_INLINE_CODE.finditer(text):
        segments.append((
            match.start(),
            match.end(),
            match.group(1),
            ("md_inline_code",),
            None,
        ))

    # 2. Links [text](url)
    for match in _RE_LINK.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_link",),
                match.group(2),
            ))

    # 3. Bold+italic ***text***
    for match in _RE_BOLD_ITALIC.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_bold", "md_italic"),
                None,
            ))

    # 4. Bold **text** / __text__
    for match in _RE_BOLD_ASTERISK.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_bold",),
                None,
            ))
    for match in _RE_BOLD_UNDERSCORE.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_bold",),
                None,
            ))

    # 5. Italic *text* / _text_
    for match in _RE_ITALIC_ASTERISK.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_italic",),
                None,
            ))
    for match in _RE_ITALIC_UNDERSCORE.finditer(text):
        if not _overlaps(segments, match.start(), match.end()):
            segments.append((
                match.start(),
                match.end(),
                match.group(1),
                ("md_italic",),
                None,
            ))

    # Sort segments by start position
    segments.sort(key=lambda s: s[0])

    # Insert text segment by segment
    global _link_counter
    pos = 0
    for start, end, content, extra_tags, url in segments:
        # Insert plain text before this segment
        if start > pos:
            plain = text[pos:start]
            text_widget.insert(tk.END, plain, tags)
        # Insert the formatted segment with combined tags
        combined_tags = tags + extra_tags

        # Handle link segments: create unique tag with click binding
        if url is not None:
            link_tag_name = f"md_link_{_link_counter}"
            _link_counter += 1
            # Configure the unique tag with the same styling as md_link
            text_widget.tag_configure(
                link_tag_name,
                foreground=MARKDOWN_TAGS["md_link"]["foreground"],
                underline=MARKDOWN_TAGS["md_link"]["underline"],
            )
            # Bind click event only for valid URLs
            if _is_valid_url(url):
                # Use default argument to capture url in closure
                text_widget.tag_bind(
                    link_tag_name,
                    "<Button-1>",
                    lambda e, u=url: webbrowser.open(u),
                )
            # Apply both md_link and the unique link tag
            combined_tags = combined_tags + (link_tag_name,)

        text_widget.insert(tk.END, content, combined_tags)
        pos = end

    # Insert any remaining plain text after the last segment
    if pos < len(text):
        text_widget.insert(tk.END, text[pos:], tags)


def _overlaps(
    segments: list[tuple[int, int, str, tuple[str, ...], str | None]],
    start: int,
    end: int,
) -> bool:
    """Check if a range overlaps with any existing segment."""
    for seg_start, seg_end, _, _, _ in segments:
        if start < seg_end and end > seg_start:
            return True
    return False


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------

_HRULE_CHAR = "\u2500"  # Box-drawing horizontal line character
_HRULE_LINE = _HRULE_CHAR * 32


def _render_header(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a header block."""
    tags = (base_tag, f"md_h{block.level}") if base_tag else (f"md_h{block.level}",)
    render_inline(text_widget, block.content, tags)
    text_widget.insert(tk.END, "\n", tags)


def _render_code_block(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a fenced code block (no inline parsing)."""
    tags = (base_tag, "md_code_block") if base_tag else ("md_code_block",)
    text_widget.insert(tk.END, block.content, tags)
    text_widget.insert(tk.END, "\n", tags)


def _render_ulist(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render an unordered list block."""
    items = block.content.split("\n")
    levels = block.meta.get("levels", [1] * len(items))
    for i, item in enumerate(items):
        level = min(levels[i] if i < len(levels) else 1, 3)
        tag_name = f"md_list_{level}"
        tags = (base_tag, tag_name) if base_tag else (tag_name,)
        text_widget.insert(tk.END, "\u2022 ", tags)
        render_inline(text_widget, item, tags)
        text_widget.insert(tk.END, "\n", tags)


def _render_olist(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render an ordered list block."""
    items = block.content.split("\n")
    levels = block.meta.get("levels", [1] * len(items))
    for i, item in enumerate(items):
        level = min(levels[i] if i < len(levels) else 1, 3)
        tag_name = f"md_list_{level}"
        tags = (base_tag, tag_name) if base_tag else (tag_name,)
        text_widget.insert(tk.END, f"{i + 1}. ", tags)
        render_inline(text_widget, item, tags)
        text_widget.insert(tk.END, "\n", tags)


def _render_blockquote(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a blockquote block."""
    tags = (base_tag, "md_blockquote") if base_tag else ("md_blockquote",)
    lines = block.content.split("\n")
    for line in lines:
        render_inline(text_widget, line, tags)
        text_widget.insert(tk.END, "\n", tags)


def _render_table(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a table block with aligned columns."""
    rows = block.content.split("\n")
    # Parse each row into cells
    parsed_rows: list[list[str]] = []
    separator_indices: set[int] = set()
    for i, row in enumerate(rows):
        # Strip leading/trailing pipes and split
        stripped = row.strip()
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        cells = [c.strip() for c in stripped.split("|")]
        # Detect separator row (all cells match ---+ pattern)
        if all(re.match(r"^:?-{2,}:?$", c.strip()) for c in cells if c.strip()):
            separator_indices.add(i)
        else:
            parsed_rows.append(cells)

    if not parsed_rows:
        return

    # Determine column widths
    num_cols = max(len(row) for row in parsed_rows)
    col_widths = [0] * num_cols
    for row in parsed_rows:
        for j, cell in enumerate(row):
            if j < num_cols:
                col_widths[j] = max(col_widths[j], len(cell))

    # Render rows
    is_header = True
    for row in parsed_rows:
        if is_header:
            tags = (base_tag, "md_table_header") if base_tag else ("md_table_header",)
            is_header = False
        else:
            tags = (base_tag, "md_table") if base_tag else ("md_table",)
        # Format cells with padding
        formatted_cells = []
        for j in range(num_cols):
            cell = row[j] if j < len(row) else ""
            formatted_cells.append(cell.ljust(col_widths[j]))
        line = " | ".join(formatted_cells)
        text_widget.insert(tk.END, line, tags)
        text_widget.insert(tk.END, "\n", tags)


def _render_hrule(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a horizontal rule."""
    tags = (base_tag, "md_hrule") if base_tag else ("md_hrule",)
    text_widget.insert(tk.END, _HRULE_LINE, tags)
    text_widget.insert(tk.END, "\n", tags)


def _render_paragraph(text_widget: tk.Text, block: Block, base_tag: str) -> None:
    """Render a paragraph block."""
    tags = (base_tag,) if base_tag else ()
    render_inline(text_widget, block.content, tags)
    text_widget.insert(tk.END, "\n", tags)


_BLOCK_RENDERERS: dict[str, callable] = {
    "header": _render_header,
    "code": _render_code_block,
    "ulist": _render_ulist,
    "olist": _render_olist,
    "blockquote": _render_blockquote,
    "table": _render_table,
    "hrule": _render_hrule,
    "paragraph": _render_paragraph,
}


def render_block(text_widget: tk.Text, block: Block, base_tag: str = "") -> None:
    """Render a single block element into the text widget.

    Dispatches to the appropriate renderer based on block.kind.

    Args:
        text_widget: The tk.Text widget to insert content into.
        block: The Block instance to render.
        base_tag: Optional base tag to apply to all inserted text.
    """
    renderer = _BLOCK_RENDERERS.get(block.kind)
    if renderer:
        renderer(text_widget, block, base_tag)
    else:
        # Fallback: treat unknown block kinds as paragraphs
        _render_paragraph(text_widget, block, base_tag)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_markdown(text_widget: tk.Text, content: str, base_tag: str = "") -> None:
    """Parse markdown content and insert formatted text into the widget.

    Args:
        text_widget: The tk.Text widget to insert content into.
        content: The raw markdown string to render.
        base_tag: Optional base tag to apply to all inserted text
                  (e.g., "assistant_msg").
    """
    # Handle empty input as no-op
    if not content:
        return

    try:
        blocks = parse_blocks(content)
        for i, block in enumerate(blocks):
            render_block(text_widget, block, base_tag)
            # Add a newline between blocks for visual spacing, but not after the last block
            if i < len(blocks) - 1:
                tags = (base_tag,) if base_tag else ()
                text_widget.insert(tk.END, "\n", tags)
    except Exception:
        # Never raise exceptions to caller — fall back to plain text insertion
        text_widget.insert(tk.END, content, (base_tag,) if base_tag else ())
