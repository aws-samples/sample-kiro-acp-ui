"""Property-based tests for link counter isolation.

**Property 2: Link counters are isolated per widget instance**

For any two distinct Text widget instances and any sequence of link renders,
the link counter for each widget SHALL increment independently — rendering N
links in widget A and M links in widget B results in widget A's counter at N
and widget B's counter at M, regardless of render order.

**Validates: Requirements 3.1, 3.2**
"""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.markdown_renderer import _get_link_counter


def _make_mock_widget():
    """Create a mock that behaves like a tkinter Text widget for attribute storage."""
    widget = MagicMock()
    # Remove the _md_link_counter attribute so getattr falls back to default
    del widget._md_link_counter
    return widget


# Strategy for the number of links to render in each widget (0 to 50)
link_counts = st.integers(min_value=0, max_value=50)

# Strategy for interleaving patterns: a list of booleans where True means
# "render in widget A" and False means "render in widget B"
interleaving_strategy = st.lists(st.booleans(), min_size=0, max_size=100)


# **Validates: Requirements 3.1, 3.2**
@settings(max_examples=200, deadline=None)
@given(n=link_counts, m=link_counts)
def test_link_counters_isolated_sequential(n, m):
    """Property 2: Sequential rendering — N links in A then M links in B.

    Rendering N links in widget A followed by M links in widget B results in
    widget A's counter at N and widget B's counter at M.

    **Validates: Requirements 3.1, 3.2**
    """
    widget_a = _make_mock_widget()
    widget_b = _make_mock_widget()

    # Render N links in widget A
    for i in range(n):
        counter = _get_link_counter(widget_a)
        assert counter == i, f"Widget A: expected counter {i} on call {i + 1}, got {counter}"

    # Render M links in widget B
    for i in range(m):
        counter = _get_link_counter(widget_b)
        assert counter == i, f"Widget B: expected counter {i} on call {i + 1}, got {counter}"

    # Final state: widget A counter at N, widget B counter at M
    assert getattr(widget_a, "_md_link_counter", 0) == n, (
        f"Widget A final counter should be {n}, got {getattr(widget_a, '_md_link_counter', 0)}"
    )
    assert getattr(widget_b, "_md_link_counter", 0) == m, (
        f"Widget B final counter should be {m}, got {getattr(widget_b, '_md_link_counter', 0)}"
    )


# **Validates: Requirements 3.1, 3.2**
@settings(max_examples=200, deadline=None)
@given(interleaving=interleaving_strategy)
def test_link_counters_isolated_interleaved(interleaving):
    """Property 2: Interleaved rendering — counters are independent regardless of order.

    For any interleaving of link renders between two widgets, each widget's
    counter increments independently. The final counter for each widget equals
    the number of links rendered in that widget.

    **Validates: Requirements 3.1, 3.2**
    """
    widget_a = _make_mock_widget()
    widget_b = _make_mock_widget()

    count_a = 0
    count_b = 0

    for render_in_a in interleaving:
        if render_in_a:
            counter = _get_link_counter(widget_a)
            assert counter == count_a, f"Widget A: expected counter {count_a}, got {counter}"
            count_a += 1
        else:
            counter = _get_link_counter(widget_b)
            assert counter == count_b, f"Widget B: expected counter {count_b}, got {counter}"
            count_b += 1

    # Final state matches the number of renders per widget
    assert getattr(widget_a, "_md_link_counter", 0) == count_a, (
        f"Widget A final counter should be {count_a}, "
        f"got {getattr(widget_a, '_md_link_counter', 0)}"
    )
    assert getattr(widget_b, "_md_link_counter", 0) == count_b, (
        f"Widget B final counter should be {count_b}, "
        f"got {getattr(widget_b, '_md_link_counter', 0)}"
    )
