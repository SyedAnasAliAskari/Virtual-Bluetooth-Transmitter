from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace
from typing import Callable

import numpy as np

from .models import AudioDevice, AudioMode, DeviceMetrics
from .resampler import AdaptiveResampler
from .ring_buffer import AudioRingBuffer
from .sync_engine import DriftController

log = logging.getLogger(__name__)

RendererErrorHandler = Callable[[str, str], None]


class _Renderer(threading.Thread):
    """One independently cancellable WASAPI render endpoint."""

    def __init__(self, audio, pyaudio, device: AudioDevice, source_rate: int,
                 mode: AudioMode, delay_ms: float, volume: float,
                 on_error: RendererErrorHandler) -> None:
        super().__init__(name=f"render-{device.pa_index}", daemon=True)
        self.audio = audio
        self.pa = pyaudio
        self.device = device
        self.source_rate = source_rate
        self.stop_event = threading.Event()
        self.on_error = on_error
        self.block_frames = max(128, int(source_rate * 0.01))
        self._base_target_frames = int(source_rate * mode.target_buffer_ms / 1000)
        self._timing_lock = threading.Lock()
        target = self._target_for_delay(delay_ms)
        self.buffer = AudioRingBuffer(max(source_rate * 2, target * 5), channels=2)
        self.controller = DriftController(target)
        self.resampler = AdaptiveResampler(source_rate, device.sample_rate)
        self.metrics = DeviceMetrics(endpoint_id=device.endpoint_id, delay_ms=delay_ms)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._volume_lock = threading.Lock()
        self._drift_frame_accumulator = 0.0

    def _target_for_delay(self, delay_ms: float) -> int:
        # Signed fine trim is allowed, but always retain at least 10 ms of safety buffer.
        minimum = max(1, int(self.source_rate * 0.010))
        delay_frames = round(self.source_rate * float(delay_ms) / 1000)
        return max(minimum, self._base_target_frames + delay_frames)

    def cancel(self) -> None:
        self.stop_event.set()

    def feed(self, data: np.ndarray) -> None:
        if not self.stop_event.is_set():
            self.buffer.write(data)

    def set_volume(self, volume: float) -> None:
        with self._volume_lock:
            self._volume = max(0.0, min(1.0, float(volume)))

    def set_delay(self, delay_ms: float) -> None:
        """Adjust relative timing smoothly without reopening this or other endpoints."""
        with self._timing_lock:
            self.controller.target = self._target_for_delay(delay_ms)
            self.controller.integral = 0.0
            self.metrics.delay_ms = float(delay_ms)

    @property
    def volume(self) -> float:
        with self._volume_lock:
            return self._volume

    def snapshot(self) -> DeviceMetrics:
        current = replace(self.metrics)
        current.buffer_ms = self.buffer.frames * 1000 / self.source_rate
        current.underruns = self.buffer.underruns
        return current

    def run(self) -> None:
        stream = None
        error_message = ""
        try:
            stream = self.audio.open(
                format=self.pa.paFloat32, channels=self.device.channels,
                rate=self.device.sample_rate, output=True,
                output_device_index=self.device.pa_index,
                frames_per_buffer=max(128, int(self.device.sample_rate * 0.01)), start=False,
            )
            # Join the live timeline by filling to the same mode target as healthy renderers.
            target = self.controller.target
            deadline = time.perf_counter() + 3.0
            while self.buffer.frames < target and not self.stop_event.is_set():
                if time.perf_counter() >= deadline:
                    raise RuntimeError("capture did not provide audio within 3 seconds")
                time.sleep(0.005)
            if self.stop_event.is_set():
                return
            stream.start_stream()
            self.metrics.state = "running"
            while not self.stop_event.is_set():
                depth = self.buffer.frames
                with self._timing_lock:
                    ppm = self.controller.update(depth)
                    target = self.controller.target
                # Correct a user nudge by at most two source frames per 10 ms block.
                # This converges a 1–2 ms trim in under a second without a hard drop.
                target_error = depth - target
                trim_step = max(-2, min(2, target_error)) if abs(target_error) > 1 else 0
                self._drift_frame_accumulator += self.block_frames * ppm / 1_000_000
                drift_step = int(self._drift_frame_accumulator)
                self._drift_frame_accumulator -= drift_step
                source_frames = max(2, self.block_frames + trim_step + drift_step)
                output_frames = max(
                    1, round(self.block_frames * self.device.sample_rate / self.source_rate)
                )
                rendered = self.resampler.process_to_length(
                    self.buffer.read(source_frames), output_frames
                )
                volume = self.volume
                if volume != 1.0:
                    rendered *= volume
                if self.device.channels == 1:
                    rendered = rendered.mean(axis=1, keepdims=True)
                stream.write(rendered.astype(np.float32, copy=False).tobytes(),
                             num_frames=len(rendered), exception_on_underflow=False)
                self.metrics.frames_rendered += len(rendered)
                self.metrics.drift_ppm = ppm
        except Exception as exc:
            self.metrics.state = "error"
            self.metrics.last_error = str(exc)
            log.exception("renderer failed for %s", self.device.name)
            error_message = f"{self.device.name}: {exc}"
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    log.debug("renderer close failed", exc_info=True)
            if self.metrics.state != "error":
                self.metrics.state = "stopped"
        # Publish failure only after the WASAPI stream has released its endpoint.
        if error_message:
            self.on_error(self.device.endpoint_id, error_message)


class AudioEngine:
    """One WASAPI loopback capture with a dynamic registry of independent renderers."""

    def __init__(self, on_error: RendererErrorHandler | None = None) -> None:
        self._on_error = on_error or (lambda _endpoint_id, _message: None)
        self._audio = None
        self._pyaudio = None
        self._capture = None
        self._renderers: dict[str, _Renderer] = {}
        self._lock = threading.RLock()
        self._source_rate = 0
        self._source_channels = 0
        self._mode = AudioMode.BALANCED
        self.running = False
        self.primary_name = ""
        self.primary_endpoint_id = ""

    def start(self, devices: list[AudioDevice], mode: AudioMode = AudioMode.BALANCED,
              delays_ms: dict[str, float] | None = None,
              volumes: dict[str, float] | None = None) -> None:
        if self.running:
            return
        if not devices:
            raise ValueError("select at least one output")
        import pyaudiowpatch as pyaudio

        self._audio = pyaudio.PyAudio()
        self._pyaudio = pyaudio
        self._mode = mode
        delays_ms = delays_ms or {}
        volumes = volumes or {}
        try:
            loopback = self._audio.get_default_wasapi_loopback()
            self.primary_name = str(loopback["name"]).replace(" [Loopback]", "").strip()
            self._source_rate = int(float(loopback["defaultSampleRate"]))
            self._source_channels = int(loopback["maxInputChannels"])
            default = next((device for device in devices if device.is_default), None)
            self.primary_endpoint_id = default.endpoint_id if default else ""

            def callback(in_data, frame_count, time_info, status):
                del frame_count, time_info
                if status:
                    log.warning("capture status flags: %s", status)
                audio = np.frombuffer(in_data, dtype=np.float32).reshape(
                    -1, self._source_channels
                )
                if self._source_channels == 1:
                    audio = np.repeat(audio, 2, axis=1)
                elif self._source_channels > 2:
                    audio = audio[:, :2]
                # Copy references under lock, then feed without blocking registry mutations.
                with self._lock:
                    renderers = tuple(self._renderers.values())
                for renderer in renderers:
                    renderer.feed(audio)
                return (None, pyaudio.paContinue)

            self._capture = self._audio.open(
                format=pyaudio.paFloat32, channels=self._source_channels,
                rate=self._source_rate, input=True,
                input_device_index=int(loopback["index"]),
                frames_per_buffer=max(128, int(self._source_rate * 0.01)),
                stream_callback=callback, start=True,
            )
            self.running = True
            for device in devices:
                if not device.is_default:
                    self.add_renderer(
                        device, delay_ms=delays_ms.get(device.endpoint_id, 0.0),
                        volume=volumes.get(device.endpoint_id, 1.0),
                    )
            log.info("capture=%s, renderers=%s", self.primary_name, self.renderer_ids())
        except Exception:
            self.stop()
            raise

    def add_renderer(self, device: AudioDevice, *, delay_ms: float = 0.0,
                     volume: float = 1.0) -> bool:
        """Join an output to the live timeline without touching existing renderers."""
        if not self.running or self._audio is None or self._pyaudio is None:
            raise RuntimeError("audio capture is not running")
        if device.is_default or device.endpoint_id == self.primary_endpoint_id:
            return False
        with self._lock:
            existing = self._renderers.get(device.endpoint_id)
            if existing and existing.is_alive() and not existing.stop_event.is_set():
                return False
            renderer = _Renderer(
                self._audio, self._pyaudio, device, self._source_rate, self._mode,
                delay_ms, volume, self._renderer_failed,
            )
            self._renderers[device.endpoint_id] = renderer
        renderer.start()
        log.info("renderer joined: %s", device.name)
        return True

    def remove_renderer(self, endpoint_id: str, timeout: float = 2.0) -> bool:
        """Detach one renderer; capture and other renderers remain untouched."""
        with self._lock:
            renderer = self._renderers.pop(endpoint_id, None)
        if renderer is None:
            return False
        renderer.cancel()
        if renderer.is_alive() and renderer is not threading.current_thread():
            renderer.join(timeout=timeout)
            if renderer.is_alive():
                log.warning("renderer did not stop within %.1fs: %s", timeout, endpoint_id)
        log.info("renderer removed: %s", renderer.device.name)
        return True

    def set_renderer_volume(self, endpoint_id: str, volume: float) -> bool:
        with self._lock:
            renderer = self._renderers.get(endpoint_id)
        if renderer is None:
            return False
        renderer.set_volume(volume)
        return True

    def set_renderer_delay(self, endpoint_id: str, delay_ms: float) -> bool:
        with self._lock:
            renderer = self._renderers.get(endpoint_id)
        if renderer is None:
            return False
        renderer.set_delay(delay_ms)
        return True

    def has_renderer(self, endpoint_id: str) -> bool:
        with self._lock:
            renderer = self._renderers.get(endpoint_id)
            return bool(renderer and renderer.is_alive() and not renderer.stop_event.is_set())

    def renderer_ids(self) -> set[str]:
        with self._lock:
            return set(self._renderers)

    def _renderer_failed(self, endpoint_id: str, message: str) -> None:
        # Called by the failing renderer: remove only that instance and never join self.
        with self._lock:
            current = self._renderers.get(endpoint_id)
            if current is threading.current_thread():
                self._renderers.pop(endpoint_id, None)
        self._on_error(endpoint_id, message)

    def stop(self) -> None:
        with self._lock:
            renderers = tuple(self._renderers.values())
            self._renderers.clear()
        for renderer in renderers:
            renderer.cancel()
        if self._capture is not None:
            try:
                self._capture.stop_stream()
                self._capture.close()
            except Exception:
                log.debug("capture close failed", exc_info=True)
            self._capture = None
        for renderer in renderers:
            if renderer.is_alive() and renderer is not threading.current_thread():
                renderer.join(timeout=2)
        stuck = [renderer for renderer in renderers if renderer.is_alive()]
        if self._audio is not None:
            if stuck:
                # Terminating PortAudio while a WASAPI write is still blocked can
                # crash the native process. Let the daemon renderer release it.
                log.warning("Deferring PortAudio termination; %d renderer(s) still closing", len(stuck))
            else:
                try:
                    self._audio.terminate()
                except Exception:
                    log.debug("PortAudio termination failed", exc_info=True)
            self._audio = None
        self._pyaudio = None
        self.running = False

    def metrics(self) -> list[DeviceMetrics]:
        with self._lock:
            renderers = tuple(self._renderers.values())
        return [renderer.snapshot() for renderer in renderers]
