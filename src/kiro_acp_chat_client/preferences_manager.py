"""Manages reading and writing user preferences for model and mode selections."""

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Preferences:
    """User's persisted model and mode selections."""

    model_id: str = "auto"
    mode_id: str = ""
    log_message_content: bool = False

    def to_dict(self) -> dict:
        """Serialize to a dict for JSON storage."""
        return {
            "model_id": self.model_id,
            "mode_id": self.mode_id,
            "log_message_content": self.log_message_content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Preferences":
        """Deserialize from a dict. Returns defaults for missing/invalid keys."""
        return cls(
            model_id=data.get("model_id", "auto") if isinstance(data.get("model_id"), str) else "auto",
            mode_id=data.get("mode_id", "") if isinstance(data.get("mode_id"), str) else "",
            log_message_content=bool(data.get("log_message_content", False)),
        )


class PreferencesManager:
    """Manages reading/writing preferences.json."""

    def __init__(self, file_path: str) -> None:
        """Initialize with the path to preferences.json."""
        self._file_path = file_path

    def load(self) -> Preferences:
        """Load preferences from disk.

        Returns defaults if file doesn't exist or is malformed JSON.
        """
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return Preferences()
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Malformed preferences file '%s': %s", self._file_path, e)
            return Preferences()
        except OSError as e:
            logger.warning("Could not read preferences file '%s': %s", self._file_path, e)
            return Preferences()

        if not isinstance(data, dict):
            logger.warning("Preferences file '%s' does not contain a JSON object", self._file_path)
            return Preferences()

        return Preferences.from_dict(data)

    def save(self, preferences: Preferences) -> None:
        """Write preferences to disk as valid JSON.

        Creates the file if it doesn't exist. Overwrites if it does.
        """
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(preferences.to_dict(), f, indent=2)
                f.write("\n")
        except OSError as e:
            logger.error("Failed to write preferences file '%s': %s", self._file_path, e)
