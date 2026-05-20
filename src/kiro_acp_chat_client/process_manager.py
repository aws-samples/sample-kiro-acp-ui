"""Process Manager for the kiro-cli acp subprocess lifecycle."""

import asyncio
import json
import logging
import signal

logger = logging.getLogger(__name__)


class ProcessStartError(Exception):
    """Raised when the kiro-cli acp process fails to start.

    This covers: binary not found, process exits during startup, or timeout.
    """


class ProcessTerminatedError(Exception):
    """Raised when the kiro-cli acp process has terminated unexpectedly.

    This is raised during read/write operations when the process is no longer alive.
    """


class ProcessManager:
    """Manages the kiro-cli acp subprocess lifecycle.

    Spawns the subprocess, provides async read/write for JSON messages
    over stdin/stdout, and handles graceful shutdown.
    """

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task | None = None
        self._read_buffer = b""

    async def start(self, timeout: float = 10.0) -> None:
        """Spawn kiro-cli acp and wait for it to be ready.

        Args:
            timeout: Maximum seconds to wait for the process to start.

        Raises:
            ProcessStartError: If binary not found, process exits, or timeout.
        """
        try:
            self._process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "kiro-cli",
                    "acp",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )
        except FileNotFoundError:
            raise ProcessStartError(
                "Could not find kiro-cli. Please ensure it is installed and on your PATH."
            ) from None
        except TimeoutError:
            raise ProcessStartError(
                "kiro-cli did not respond within the timeout period. Please try restarting."
            ) from None
        except OSError as e:
            raise ProcessStartError(f"Failed to start kiro-cli: {e}") from e

        # Check if the process exited immediately after spawning
        if self._process.returncode is not None:
            raise ProcessStartError(
                f"kiro-cli exited unexpectedly (code: {self._process.returncode}). "
                "Please check your installation."
            )

        # Start background task to drain stderr so it doesn't block the process
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        """Continuously read and log stderr to prevent buffer blocking."""
        try:
            while self._process and self._process.returncode is None:
                if self._process.stderr:
                    line = await self._process.stderr.readline()
                    if not line:
                        break
                    logger.warning(
                        "kiro-cli stderr: %s", line.decode("utf-8", errors="replace").rstrip()[:500]
                    )
                else:
                    break
        except Exception as e:  # nosec B110 — intentional: prevent stderr reader from crashing app
            logger.debug("stderr reader terminated: %s", e)

    async def write_message(self, message: dict) -> None:
        """Write a JSON-RPC message to the subprocess stdin.

        Serializes the dict to JSON, appends a newline, and writes to stdin.

        Args:
            message: A dictionary representing a JSON-RPC message.

        Raises:
            ProcessTerminatedError: If the process is not running.
        """
        if not self.is_running:
            raise ProcessTerminatedError("Cannot write: process is not running.")

        assert self._process is not None
        assert self._process.stdin is not None
        line = json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
        # Log method/id only — message bodies may contain sensitive user content
        method = message.get("method", "response")
        msg_id = message.get("id", "-")
        logger.debug(">>> [id=%s] %s", msg_id, method)
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

    async def read_message(self) -> dict:
        """Read a single JSON-RPC message from subprocess stdout.

        Reads raw bytes until a newline is found, then parses as JSON.
        This avoids asyncio StreamReader's line length limits.

        Returns:
            A dictionary representing the parsed JSON-RPC message.

        Raises:
            ProcessTerminatedError: If the process has exited or stdout is closed.
        """
        if not self.is_running:
            raise ProcessTerminatedError("Cannot read: process is not running.")

        assert self._process is not None
        assert self._process.stdout is not None

        # Read until we have a complete line (newline-delimited JSON)
        while b"\n" not in self._read_buffer:
            try:
                chunk = await self._process.stdout.read(65536)  # 64KB chunks
            except Exception as e:
                logger.warning("Read error: %s", e)
                raise ProcessTerminatedError(
                    "Connection to Kiro lost. Please restart the application."
                ) from e
            if not chunk:
                # EOF — process closed stdout
                returncode = self._process.returncode
                logger.warning(
                    "kiro-cli stdout EOF. Exit code: %s, buffer size: %d",
                    returncode,
                    len(self._read_buffer),
                )
                if self._read_buffer:
                    logger.warning(
                        "Partial buffer content: %s",
                        self._read_buffer[:500].decode("utf-8", errors="replace"),
                    )
                raise ProcessTerminatedError(
                    "Connection to Kiro lost. Please restart the application."
                )
            self._read_buffer += chunk

        # Split on first newline
        line_bytes, self._read_buffer = self._read_buffer.split(b"\n", 1)

        # Skip empty lines and non-JSON lines (kiro-cli sometimes writes log output to stdout)
        line = line_bytes.decode("utf-8").strip()
        while not line or not line.startswith("{"):
            # Read the next line
            while b"\n" not in self._read_buffer:
                try:
                    chunk = await self._process.stdout.read(65536)
                except Exception as e:
                    logger.warning("Read error: %s", e)
                    raise ProcessTerminatedError(
                        "Connection to Kiro lost. Please restart the application."
                    ) from e
                if not chunk:
                    returncode = self._process.returncode
                    logger.warning(
                        "kiro-cli stdout EOF. Exit code: %s, buffer size: %d",
                        returncode,
                        len(self._read_buffer),
                    )
                    raise ProcessTerminatedError(
                        "Connection to Kiro lost. Please restart the application."
                    )
                self._read_buffer += chunk
            line_bytes, self._read_buffer = self._read_buffer.split(b"\n", 1)
            line = line_bytes.decode("utf-8").strip()

        # Log method/id only — response bodies may contain sensitive content
        parsed: dict = json.loads(line)
        method = parsed.get("method", "response")
        msg_id = parsed.get("id", "-")
        logger.debug("<<< [id=%s] %s", msg_id, method)
        return parsed

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully terminate the subprocess.

        Sends SIGTERM, waits up to timeout seconds for the process to exit,
        then sends SIGKILL if it's still running.

        Args:
            timeout: Maximum seconds to wait after SIGTERM before sending SIGKILL.
        """
        if self._process is None or self._process.returncode is not None:
            return

        try:
            self._process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            # Process already exited
            return

        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except TimeoutError:
            # Process didn't exit gracefully, force kill
            try:
                self._process.kill()
                await self._process.wait()
            except ProcessLookupError:
                pass

    @property
    def is_running(self) -> bool:
        """Whether the subprocess is currently alive."""
        return self._process is not None and self._process.returncode is None
