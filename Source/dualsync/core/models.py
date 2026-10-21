from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class AudioMode(StrEnum):
    LOW_LATENCY = "Low Latency"
    BALANCED = "Balanced"
    STABLE = "Stable"

    @property
    def target_buffer_ms(self) -> int:
        return {self.LOW_LATENCY: 45, self.BALANCED: 90, self.STABLE: 160}[self]


@dataclass(slots=True)
class AudioDevice:
    endpoint_id: str
    name: str
    pa_index: int
    channels: int
    sample_rate: int
    available: bool = True
    is_default: bool = False
    is_bluetooth: bool = False
    supported_formats: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeviceMetrics:
    endpoint_id: str
    buffer_ms: float = 0.0
    drift_ppm: float = 0.0
    delay_ms: float = 0.0
    underruns: int = 0
    frames_rendered: int = 0
    state: str = "stopped"
    last_error: str = ""


@dataclass(slots=True)
class CalibrationRecord:
    endpoint_id: str
    delay_ms: float
    method: str = "manual"
    confidence: float = 0.0
    samples: int = 0
    calibrated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)
