from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import app_data_dir


@dataclass
class AudioProfile:
    name: str
    endpoint_ids: list[str]
    endpoint_names: dict[str, str]
    delays_ms: dict[str, float] = field(default_factory=dict)
    mode: str = "Balanced"


class ProfileManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or app_data_dir() / "profiles.json"

    def load_all(self) -> list[AudioProfile]:
        try:
            return [AudioProfile(**item) for item in json.loads(self.path.read_text("utf-8"))]
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return []

    def save(self, profile: AudioProfile) -> None:
        profiles = {item.name: item for item in self.load_all()}
        profiles[profile.name] = profile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(item) for item in profiles.values()], indent=2), "utf-8")
        os.replace(tmp, self.path)

    def delete(self, name: str) -> None:
        profiles = [item for item in self.load_all() if item.name != name]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(item) for item in profiles], indent=2), "utf-8")
