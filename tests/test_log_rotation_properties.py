"""Property-based tests for log rotation correctness.

**Property 6: Log rotation retains exactly the N most recent files**

For any set of K log files matching the pattern `kiro-acp-chat-*.log` where
K > 10, after rotation exactly 10 files SHALL remain, and they SHALL be the
10 files with the lexicographically greatest filenames (most recent by
timestamp encoding).

**Validates: Requirements 11.2**
"""

from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.__main__ import _rotate_logs

# Strategy for generating a list of unique timestamp-style suffixes.
# We generate between 11 and 50 log files (K > 10) with realistic
# timestamp-encoded filenames (YYYYMMDD-HHMMSS format).
_timestamp_strategy = st.builds(
    lambda y, mo, d, h, mi, s: f"{y:04d}{mo:02d}{d:02d}-{h:02d}{mi:02d}{s:02d}",
    y=st.integers(min_value=2020, max_value=2030),
    mo=st.integers(min_value=1, max_value=12),
    d=st.integers(min_value=1, max_value=28),
    h=st.integers(min_value=0, max_value=23),
    mi=st.integers(min_value=0, max_value=59),
    s=st.integers(min_value=0, max_value=59),
)

# Generate a list of unique timestamps with more than 10 entries
_log_file_timestamps = st.lists(
    _timestamp_strategy,
    min_size=11,
    max_size=50,
    unique=True,
)


# **Validates: Requirements 11.2**
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(timestamps=_log_file_timestamps)
def test_rotation_retains_exactly_10_most_recent_files(
    tmp_path: Path, timestamps: list[str]
) -> None:
    """Property 6: Log rotation retains exactly the N most recent files.

    For any set of K log files matching the pattern `kiro-acp-chat-*.log`
    where K > 10, after calling _rotate_logs(), exactly 10 files remain,
    and they are the 10 files with the lexicographically greatest filenames
    (most recent by timestamp encoding).

    # Feature: github-issues-backlog, Property 6: Log rotation retains exactly
    # the N most recent files

    **Validates: Requirements 11.2**
    """
    # Create a unique subdirectory per test example to avoid interference
    test_dir = tmp_path / "logs"
    test_dir.mkdir(exist_ok=True)

    # Clean any files from previous hypothesis examples in this tmp_path
    for f in test_dir.glob("kiro-acp-chat-*.log"):
        f.unlink()

    # Create log files with the generated timestamps
    filenames = [f"kiro-acp-chat-{ts}.log" for ts in timestamps]
    for name in filenames:
        (test_dir / name).touch()

    k = len(timestamps)
    assert k > 10, "Precondition: more than 10 log files must exist"

    # Perform rotation
    _rotate_logs(test_dir)

    # Verify exactly 10 files remain
    remaining = sorted(test_dir.glob("kiro-acp-chat-*.log"))
    assert len(remaining) == 10, (
        f"Expected exactly 10 files after rotation of {k} files, but got {len(remaining)}"
    )

    # Verify the remaining files are the 10 lexicographically greatest
    expected_remaining = sorted(filenames, reverse=True)[:10]
    actual_remaining = sorted([f.name for f in remaining], reverse=True)

    assert actual_remaining == expected_remaining, (
        f"Remaining files should be the 10 most recent (lexicographically greatest).\n"
        f"Expected: {sorted(expected_remaining)}\n"
        f"Actual:   {sorted(actual_remaining)}"
    )
