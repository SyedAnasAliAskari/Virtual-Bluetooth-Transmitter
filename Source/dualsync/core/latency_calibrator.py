from __future__ import annotations

import math
import time

import numpy as np

from .models import AudioDevice, CalibrationRecord


def software_calibration(devices: list[AudioDevice]) -> list[CalibrationRecord]:
    """Estimate relative host buffering; this is not acoustic Bluetooth latency."""
    if not devices:
        return []
    # Active shared-mode endpoints expose little reliable latency metadata through PA.
    # Use sample-period quantization only and deliberately report low confidence.
    periods = {item.endpoint_id: 1000.0 * 480 / item.sample_rate for item in devices}
    slowest = max(periods.values())
    return [
        CalibrationRecord(
            endpoint_id=item.endpoint_id,
            delay_ms=max(0.0, slowest - periods[item.endpoint_id]),
            method="software-estimate",
            confidence=0.15,
            samples=1,
        )
        for item in devices
    ]


def make_chirp(rate: int, duration: float = 0.18) -> np.ndarray:
    frames = int(rate * duration)
    t = np.arange(frames, dtype=np.float64) / rate
    phase = 2 * np.pi * (900 * t + (5200 - 900) / (2 * duration) * t * t)
    envelope = np.sin(np.pi * np.minimum(t / duration, 1.0)) ** 2
    return (0.35 * np.sin(phase) * envelope).astype(np.float32)


def estimate_arrival(recording: np.ndarray, reference: np.ndarray, rate: int) -> tuple[float, float]:
    """Return arrival milliseconds and normalized correlation confidence."""
    signal = recording.mean(axis=1) if recording.ndim == 2 else recording
    signal = signal.astype(np.float64) - float(np.mean(signal))
    ref = reference.astype(np.float64) - float(np.mean(reference))
    correlation = np.correlate(signal, ref, mode="valid")
    index = int(np.argmax(np.abs(correlation)))
    denom = math.sqrt(float(np.dot(ref, ref)) * float(np.dot(signal[index:index + len(ref)], signal[index:index + len(ref)])))
    confidence = 0.0 if denom == 0 else min(1.0, abs(float(correlation[index])) / denom)
    return index * 1000.0 / rate, confidence


class AcousticCalibrator:
    """Microphone-assisted relative measurement using sequential chirp playback."""

    def measure(self, devices: list[AudioDevice], repeats: int = 3) -> list[CalibrationRecord]:
        import pyaudiowpatch as pyaudio

        if len(devices) < 2:
            raise ValueError("acoustic calibration needs at least two outputs")
        pa = pyaudio.PyAudio()
        arrivals: dict[str, list[tuple[float, float]]] = {d.endpoint_id: [] for d in devices}
        rate = 48000
        chirp = make_chirp(rate)
        silence = np.zeros((int(rate * 0.25), 2), np.float32)
        stereo = np.repeat(chirp[:, None], 2, axis=1)
        payload = np.concatenate((silence, stereo, silence))
        try:
            mic = pa.get_default_input_device_info()
            channels = min(2, int(mic["maxInputChannels"]))
            if channels < 1:
                raise RuntimeError("no default microphone is available")
            for device in devices:
                for _ in range(max(2, min(7, repeats))):
                    capture = pa.open(format=pyaudio.paFloat32, channels=channels, rate=rate,
                                      input=True, input_device_index=int(mic["index"]),
                                      frames_per_buffer=480)
                    output = pa.open(format=pyaudio.paFloat32, channels=device.channels, rate=rate,
                                     output=True, output_device_index=device.pa_index,
                                     frames_per_buffer=480)
                    capture.start_stream()
                    output_data = payload if device.channels == 2 else payload.mean(axis=1, keepdims=True)
                    output.write(output_data.tobytes(), num_frames=len(output_data))
                    raw = capture.read(len(payload) + rate // 2, exception_on_overflow=False)
                    output.close()
                    capture.close()
                    recording = np.frombuffer(raw, np.float32).reshape(-1, channels)
                    arrivals[device.endpoint_id].append(estimate_arrival(recording, chirp, rate))
                    time.sleep(0.12)
        finally:
            pa.terminate()
        median_arrival = {key: float(np.median([v[0] for v in values])) for key, values in arrivals.items()}
        slowest = max(median_arrival.values())
        return [
            CalibrationRecord(
                endpoint_id=device.endpoint_id,
                delay_ms=max(0.0, slowest - median_arrival[device.endpoint_id]),
                method="microphone-acoustic",
                confidence=float(np.median([v[1] for v in arrivals[device.endpoint_id]])),
                samples=len(arrivals[device.endpoint_id]),
            )
            for device in devices
        ]
