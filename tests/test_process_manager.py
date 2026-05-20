"""Unit tests for the ProcessManager class."""

import asyncio
import json
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kiro_acp_chat_client.process_manager import (
    ProcessManager,
    ProcessStartError,
    ProcessTerminatedError,
)


def make_mock_process(returncode=None):
    """Create a mock asyncio subprocess."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.stdout = MagicMock()
    proc.stdout.readline = AsyncMock()
    proc.stdout.read = AsyncMock()
    proc.stderr = MagicMock()
    proc.stderr.readline = AsyncMock(return_value=b"")
    proc.send_signal = MagicMock()
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


class TestProcessManagerStart:
    @pytest.mark.asyncio
    async def test_successful_start(self):
        mock_proc = make_mock_process(returncode=None)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            pm = ProcessManager()
            await pm.start(timeout=5.0)

            assert pm.is_running is True
            mock_exec.assert_called_once_with(
                "kiro-cli",
                "acp",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_binary_not_found_raises_process_start_error(self):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = FileNotFoundError("No such file")
            pm = ProcessManager()

            with pytest.raises(ProcessStartError, match="Could not find kiro-cli"):
                await pm.start()

    @pytest.mark.asyncio
    async def test_process_exits_immediately_raises_process_start_error(self):
        mock_proc = make_mock_process(returncode=1)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            pm = ProcessManager()

            with pytest.raises(ProcessStartError, match="exited unexpectedly"):
                await pm.start()

    @pytest.mark.asyncio
    async def test_timeout_raises_process_start_error(self):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError()

            with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for:
                mock_wait_for.side_effect = TimeoutError()
                pm = ProcessManager()

                with pytest.raises(ProcessStartError, match="did not respond"):
                    await pm.start(timeout=1.0)

    @pytest.mark.asyncio
    async def test_os_error_raises_process_start_error(self):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = OSError("Permission denied")

            with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait_for:
                mock_wait_for.side_effect = OSError("Permission denied")
                pm = ProcessManager()

                with pytest.raises(ProcessStartError, match="Failed to start"):
                    await pm.start()


class TestProcessManagerWriteMessage:
    @pytest.mark.asyncio
    async def test_write_message_serializes_and_writes(self):
        mock_proc = make_mock_process(returncode=None)
        pm = ProcessManager()
        pm._process = mock_proc

        message = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        await pm.write_message(message)

        expected_line = json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
        mock_proc.stdin.write.assert_called_once_with(expected_line.encode("utf-8"))
        mock_proc.stdin.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_message_raises_when_process_not_running(self):
        pm = ProcessManager()
        # No process started

        with pytest.raises(ProcessTerminatedError, match="not running"):
            await pm.write_message({"jsonrpc": "2.0"})

    @pytest.mark.asyncio
    async def test_write_message_raises_when_process_exited(self):
        mock_proc = make_mock_process(returncode=1)
        pm = ProcessManager()
        pm._process = mock_proc

        with pytest.raises(ProcessTerminatedError, match="not running"):
            await pm.write_message({"jsonrpc": "2.0"})


class TestProcessManagerReadMessage:
    @pytest.mark.asyncio
    async def test_read_message_parses_valid_json(self):
        mock_proc = make_mock_process(returncode=None)
        expected = {"jsonrpc": "2.0", "id": 1, "result": {"status": "ok"}}
        mock_proc.stdout.read.return_value = (
            json.dumps(expected, separators=(",", ":")) + "\n"
        ).encode("utf-8")

        pm = ProcessManager()
        pm._process = mock_proc

        result = await pm.read_message()
        assert result == expected

    @pytest.mark.asyncio
    async def test_read_message_raises_on_eof(self):
        mock_proc = make_mock_process(returncode=None)
        mock_proc.stdout.read.return_value = b""

        pm = ProcessManager()
        pm._process = mock_proc

        with pytest.raises(ProcessTerminatedError, match="Connection to Kiro lost"):
            await pm.read_message()

    @pytest.mark.asyncio
    async def test_read_message_raises_when_process_not_running(self):
        pm = ProcessManager()

        with pytest.raises(ProcessTerminatedError, match="not running"):
            await pm.read_message()

    @pytest.mark.asyncio
    async def test_read_message_raises_when_process_exited(self):
        mock_proc = make_mock_process(returncode=0)
        pm = ProcessManager()
        pm._process = mock_proc

        with pytest.raises(ProcessTerminatedError, match="not running"):
            await pm.read_message()


class TestProcessManagerShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_sends_sigterm_then_waits(self):
        mock_proc = make_mock_process(returncode=None)
        mock_proc.wait.return_value = 0

        pm = ProcessManager()
        pm._process = mock_proc

        await pm.shutdown(timeout=5.0)

        mock_proc.send_signal.assert_called_once_with(signal.SIGTERM)
        mock_proc.wait.assert_awaited()

    @pytest.mark.asyncio
    async def test_shutdown_kills_after_timeout(self):
        mock_proc = make_mock_process(returncode=None)

        pm = ProcessManager()
        pm._process = mock_proc

        # Patch asyncio.wait_for at the module level to raise TimeoutError
        async def mock_wait_for(coro, timeout):
            # Consume the awaitable to avoid warnings
            if asyncio.iscoroutine(coro):
                coro.close()
            raise TimeoutError()

        with patch(
            "kiro_acp_chat_client.process_manager.asyncio.wait_for",
            side_effect=mock_wait_for,
        ):
            # After kill, wait should succeed
            mock_proc.wait.return_value = None
            await pm.shutdown(timeout=0.1)

        mock_proc.send_signal.assert_called_once_with(signal.SIGTERM)
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_noop_when_no_process(self):
        pm = ProcessManager()
        # Should not raise
        await pm.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_noop_when_already_exited(self):
        mock_proc = make_mock_process(returncode=0)
        pm = ProcessManager()
        pm._process = mock_proc

        # Should not raise
        await pm.shutdown()
        mock_proc.send_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_handles_process_lookup_error_on_sigterm(self):
        mock_proc = make_mock_process(returncode=None)
        mock_proc.send_signal.side_effect = ProcessLookupError()

        pm = ProcessManager()
        pm._process = mock_proc

        # Should not raise
        await pm.shutdown()


class TestProcessManagerIsRunning:
    def test_is_running_false_when_no_process(self):
        pm = ProcessManager()
        assert pm.is_running is False

    def test_is_running_true_when_process_alive(self):
        mock_proc = make_mock_process(returncode=None)
        pm = ProcessManager()
        pm._process = mock_proc
        assert pm.is_running is True

    def test_is_running_false_when_process_exited(self):
        mock_proc = make_mock_process(returncode=0)
        pm = ProcessManager()
        pm._process = mock_proc
        assert pm.is_running is False
