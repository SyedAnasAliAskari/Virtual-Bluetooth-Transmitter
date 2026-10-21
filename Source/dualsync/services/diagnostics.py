from __future__ import annotations

import json
import logging
import platform
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path

import psutil

from .config import app_data_dir


def configure_logging() -> Path:
    directory = app_data_dir() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "dualsync.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8")],
    )
    return path


def write_snapshot(devices: list, metrics: list, extra: dict | None = None) -> Path:
    process = psutil.Process()
    report = {
        "generated_unix": time.time(),
        "platform": platform.platform(),
        "python": sys.version,
        "cpu_percent": process.cpu_percent(interval=0.1),
        "rss_bytes": process.memory_info().rss,
        "devices": [asdict(item) if is_dataclass(item) else str(item) for item in devices],
        "metrics": [asdict(item) if is_dataclass(item) else str(item) for item in metrics],
        "notes": {
            "timing": "All runtime latency/drift values are software-observable estimates.",
            "acoustic": "No acoustic result is claimed without microphone calibration.",
        },
        **(extra or {}),
    }
    path = app_data_dir() / "diagnostics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    return path
