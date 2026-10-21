"""Open the live default loopback and one secondary renderer for a timed smoke test."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict

from dualsync.core.audio_engine import AudioEngine
from dualsync.core.device_manager import DeviceManager
from dualsync.core.models import AudioMode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--secondary", type=int)
    args = parser.parse_args()
    devices = DeviceManager().discover()
    default = next(item for item in devices if item.is_default)
    candidates = [item for item in devices if not item.is_default]
    if not candidates:
        raise SystemExit("No active secondary WASAPI endpoint is available")
    secondary = next((item for item in candidates if item.pa_index == args.secondary), candidates[0])
    errors: list[str] = []
    engine = AudioEngine(lambda _endpoint_id, message: errors.append(message))
    print(f"capture/default: {default.name}; secondary: {secondary.name}")
    engine.start([default, secondary], AudioMode.BALANCED)
    try:
        time.sleep(args.seconds)
        print(json.dumps([asdict(item) for item in engine.metrics()], indent=2))
    finally:
        engine.stop()
    if errors:
        print(json.dumps({"errors": errors}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
