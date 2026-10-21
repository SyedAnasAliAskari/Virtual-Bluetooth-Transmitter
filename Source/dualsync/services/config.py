from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dualsync.core.models import AudioMode, CalibrationRecord

log = logging.getLogger(__name__)


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "DualSync"


@dataclass
class AppSettings:
    start_with_windows: bool = False
    auto_resume: bool = False
    auto_rejoin: bool = True
    restore_devices: bool = True
    notifications: bool = True
    max_outputs: int = 5
    mode: str = AudioMode.BALANCED.value
    selected_endpoint_ids: list[str] = field(default_factory=list)
    device_enabled: dict[str, bool] = field(default_factory=dict)
    device_volumes: dict[str, float] = field(default_factory=dict)
    known_device_names: dict[str, str] = field(default_factory=dict)
    delays_ms: dict[str, float] = field(default_factory=dict)
    calibrations: dict[str, dict] = field(default_factory=dict)
    was_running: bool = False

    @classmethod
    def from_dict(cls, raw: dict) -> "AppSettings":
        allowed = cls.__dataclass_fields__.keys()
        data = {key: value for key, value in raw.items() if key in allowed}
        result = cls(**data)
        result.max_outputs = max(2, min(5, int(result.max_outputs)))
        if result.mode not in {item.value for item in AudioMode}:
            result.mode = AudioMode.BALANCED.value
        result.device_volumes = {
            key: max(0.0, min(1.0, float(value)))
            for key, value in result.device_volumes.items()
        }
        return result

    def set_calibration(self, record: CalibrationRecord) -> None:
        self.calibrations[record.endpoint_id] = record.to_dict()
        self.delays_ms[record.endpoint_id] = record.delay_ms


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> AppSettings:
        try:
            return AppSettings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            return AppSettings()
        except (json.JSONDecodeError, TypeError, ValueError):
            broken = self.path.with_suffix(".invalid.json")
            try:
                self.path.replace(broken)
            except OSError:
                pass
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False,
                prefix="settings-", suffix=".tmp",
            ) as temporary:
                temporary.write(json.dumps(asdict(settings), indent=2))
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, self.path)
        except OSError:
            log.exception("Could not save DualSync settings")
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def reset(self) -> None:
        self.path.unlink(missing_ok=True)
