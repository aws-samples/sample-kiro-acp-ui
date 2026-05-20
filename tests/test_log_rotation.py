"""Unit tests for the _rotate_logs function in __main__.py."""

from pathlib import Path

from kiro_acp_chat_client.__main__ import _rotate_logs


class TestRotateLogs:
    """Tests for _rotate_logs function."""

    def test_no_files_does_nothing(self, tmp_path: Path) -> None:
        """When no log files exist, rotation does nothing."""
        _rotate_logs(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_fewer_than_max_keeps_all(self, tmp_path: Path) -> None:
        """When fewer than 10 log files exist, all are kept."""
        for i in range(5):
            (tmp_path / f"kiro-acp-chat-2025010{i}-120000.log").touch()
        _rotate_logs(tmp_path)
        assert len(list(tmp_path.glob("kiro-acp-chat-*.log"))) == 5

    def test_exactly_max_keeps_all(self, tmp_path: Path) -> None:
        """When exactly 10 log files exist, all are kept."""
        for i in range(10):
            (tmp_path / f"kiro-acp-chat-20250{i:02d}01-120000.log").touch()
        _rotate_logs(tmp_path)
        assert len(list(tmp_path.glob("kiro-acp-chat-*.log"))) == 10

    def test_more_than_max_deletes_oldest(self, tmp_path: Path) -> None:
        """When more than 10 log files exist, oldest are deleted."""
        for i in range(15):
            (tmp_path / f"kiro-acp-chat-202501{i:02d}-120000.log").touch()
        _rotate_logs(tmp_path)
        remaining = sorted(tmp_path.glob("kiro-acp-chat-*.log"))
        assert len(remaining) == 10
        # The 10 most recent (lexicographically greatest) should remain
        assert remaining[-1].name == "kiro-acp-chat-20250114-120000.log"
        assert remaining[0].name == "kiro-acp-chat-20250105-120000.log"

    def test_non_matching_files_are_not_deleted(self, tmp_path: Path) -> None:
        """Files not matching the pattern are left untouched."""
        for i in range(12):
            (tmp_path / f"kiro-acp-chat-202501{i:02d}-120000.log").touch()
        (tmp_path / "other-file.txt").touch()
        (tmp_path / "app.log").touch()
        _rotate_logs(tmp_path)
        assert (tmp_path / "other-file.txt").exists()
        assert (tmp_path / "app.log").exists()
        assert len(list(tmp_path.glob("kiro-acp-chat-*.log"))) == 10

    def test_oserror_on_delete_is_silenced(self, tmp_path: Path) -> None:
        """OSError during file deletion is silently handled."""
        for i in range(12):
            (tmp_path / f"kiro-acp-chat-202501{i:02d}-120000.log").touch()
        # Make the directory read-only to prevent deletion
        tmp_path.chmod(0o555)
        try:
            # The function should not raise even if unlink fails
            _rotate_logs(tmp_path)
        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(0o755)
