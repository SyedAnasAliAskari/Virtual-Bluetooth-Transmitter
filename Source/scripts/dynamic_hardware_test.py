"""Exercise live remove/rejoin behavior without claiming acoustic verification."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict

from dualsync.core.audio_engine import AudioEngine
from dualsync.core.device_manager import DeviceManager
from dualsync.core.models import AudioMode


def wait_for_running(engine: AudioEngine, endpoint_id: str, timeout: float = 4.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        match = next((m for m in engine.metrics() if m.endpoint_id == endpoint_id), None)
        if match and match.state == "running":
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    devices = DeviceManager().discover()
    primary = next((item for item in devices if item.is_default), None)
    secondary = next((item for item in devices if not item.is_default), None)
    if not primary or not secondary:
        raise SystemExit("Test needs one default and one active secondary WASAPI endpoint")
    errors: list[tuple[str, str]] = []
    engine = AudioEngine(lambda endpoint_id, message: errors.append((endpoint_id, message)))
    report = {
        "primary": primary.name,
        "secondary": secondary.name,
        "cycles": [],
        "capture_preserved": True,
    }
    before = {thread.ident for thread in threading.enumerate() if thread.name.startswith("render-")}
    engine.start(
        [primary, secondary], AudioMode.BALANCED,
        volumes={secondary.endpoint_id: 0.65},
    )
    capture = engine._capture
    try:
        if not wait_for_running(engine, secondary.endpoint_id):
            raise RuntimeError("initial secondary renderer did not reach running state")
        engine.set_renderer_volume(secondary.endpoint_id, 0.65)
        fine_offsets = [1.5, -1.5, 0.0]
        for cycle, fine_offset in enumerate(fine_offsets):
            removed = engine.remove_renderer(secondary.endpoint_id)
            capture_alive = engine.running and engine._capture is capture
            empty = not engine.renderer_ids()
            rejoined = engine.add_renderer(secondary, delay_ms=0.0, volume=0.65)
            running = wait_for_running(engine, secondary.endpoint_id)
            delay_applied = engine.set_renderer_delay(secondary.endpoint_id, fine_offset)
            time.sleep(0.75)
            metric = next(
                (item for item in engine.metrics() if item.endpoint_id == secondary.endpoint_id),
                None,
            )
            report["cycles"].append({
                "cycle": cycle + 1,
                "removed": removed,
                "capture_alive_with_no_renderers": capture_alive and empty,
                "rejoined": rejoined,
                "running": running,
                "fine_offset_ms": fine_offset,
                "delay_applied": delay_applied,
                "reported_delay_ms": metric.delay_ms if metric else None,
                "underruns": metric.underruns if metric else None,
            })
            report["capture_preserved"] &= capture_alive
        report["final_metrics"] = [asdict(item) for item in engine.metrics()]
    finally:
        engine.stop()
    time.sleep(0.2)
    after = {
        thread.ident for thread in threading.enumerate()
        if thread.name.startswith("render-") and thread.is_alive()
    }
    report["renderer_thread_leaks"] = len(after - before)
    report["errors"] = errors
    print(json.dumps(report, indent=2))
    ok = (
        not errors
        and report["capture_preserved"]
        and report["renderer_thread_leaks"] == 0
        and all(item["running"] for item in report["cycles"])
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
