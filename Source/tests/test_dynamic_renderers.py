import threading
import time
from dataclasses import replace

from dualsync.core import audio_engine
from dualsync.core.audio_engine import AudioEngine
from dualsync.core.models import AudioDevice, AudioMode, DeviceMetrics


def device(endpoint_id: str, index: int) -> AudioDevice:
    return AudioDevice(endpoint_id, endpoint_id, index, 2, 48000)


class FakeRenderer:
    def __init__(self, _audio, _pa, target, _rate, _mode, delay, volume, _on_error):
        self.device = target
        self.stop_event = threading.Event()
        self._alive = False
        self._volume = volume
        self.metrics = DeviceMetrics(target.endpoint_id, delay_ms=delay)

    def start(self):
        self._alive = True

    def is_alive(self):
        return self._alive

    def cancel(self):
        self.stop_event.set()
        self._alive = False

    def join(self, timeout=None):
        del timeout

    def set_volume(self, volume):
        self._volume = volume

    def set_delay(self, delay_ms):
        self.metrics.delay_ms = delay_ms

    def snapshot(self):
        return replace(self.metrics)


def ready_engine() -> AudioEngine:
    engine = AudioEngine()
    engine.running = True
    engine._audio = object()
    engine._pyaudio = object()
    engine._source_rate = 48000
    return engine


def test_remove_one_does_not_touch_other_or_capture(monkeypatch):
    monkeypatch.setattr(audio_engine, "_Renderer", FakeRenderer)
    engine = ready_engine()
    first, second, third = device("one", 1), device("two", 2), device("three", 3)
    engine.add_renderer(first)
    engine.add_renderer(second)
    engine.add_renderer(third)
    unaffected = engine._renderers["three"]

    assert engine.remove_renderer("two")
    assert engine.running
    assert engine.renderer_ids() == {"one", "three"}
    assert engine._renderers["three"] is unaffected


def test_disconnect_all_then_rejoin_without_restarting_capture(monkeypatch):
    monkeypatch.setattr(audio_engine, "_Renderer", FakeRenderer)
    engine = ready_engine()
    devices = [device(str(index), index) for index in range(1, 4)]
    for item in devices:
        engine.add_renderer(item)
    capture_owner = engine._audio
    for item in devices:
        engine.remove_renderer(item.endpoint_id)

    assert engine.running
    assert engine.renderer_ids() == set()
    engine.add_renderer(devices[1], delay_ms=37.5, volume=0.42)
    assert engine._audio is capture_owner
    assert engine.renderer_ids() == {"2"}
    assert engine.metrics()[0].delay_ms == 37.5
    assert engine._renderers["2"]._volume == 0.42


def test_repeated_remove_rejoin_and_volume_updates(monkeypatch):
    monkeypatch.setattr(audio_engine, "_Renderer", FakeRenderer)
    engine = ready_engine()
    target = device("repeat", 4)
    for index in range(30):
        assert engine.add_renderer(target)
        assert not engine.add_renderer(target)
        assert engine.set_renderer_volume("repeat", index / 30)
        assert engine.set_renderer_delay("repeat", (index - 15) / 10)
        assert engine.remove_renderer("repeat")
    assert engine.renderer_ids() == set()
    assert engine.running


class FakePA:
    paFloat32 = 1


class QuietStream:
    def start_stream(self):
        pass

    def write(self, _data, num_frames, exception_on_underflow):
        del num_frames, exception_on_underflow
        time.sleep(0.002)

    def stop_stream(self):
        pass

    def close(self):
        pass


class SelectiveAudio:
    def open(self, **kwargs):
        if kwargs["output_device_index"] == 9:
            raise OSError("endpoint vanished")
        return QuietStream()


def test_renderer_failure_does_not_cancel_healthy_renderer():
    failures = []
    engine = AudioEngine(lambda endpoint_id, message: failures.append((endpoint_id, message)))
    engine.running = True
    engine._audio = SelectiveAudio()
    engine._pyaudio = FakePA()
    engine._source_rate = 48000
    healthy = device("healthy", 8)
    failing = device("failing", 9)
    engine.add_renderer(healthy)
    engine.add_renderer(failing)
    deadline = time.time() + 2
    while "failing" in engine.renderer_ids() and time.time() < deadline:
        time.sleep(0.01)

    assert engine.renderer_ids() == {"healthy"}
    assert engine.has_renderer("healthy")
    assert failures and failures[0][0] == "failing"
    engine.remove_renderer("healthy")


def test_fractional_delay_changes_renderer_timeline_target():
    renderer = audio_engine._Renderer(
        None, None, device("fine", 10), 48000, AudioMode.BALANCED,
        1.5, 1.0, lambda _endpoint_id, _message: None,
    )
    assert renderer.controller.target == 4392
    renderer.set_delay(-1.5)
    assert renderer.controller.target == 4248
    assert renderer.snapshot().delay_ms == -1.5
