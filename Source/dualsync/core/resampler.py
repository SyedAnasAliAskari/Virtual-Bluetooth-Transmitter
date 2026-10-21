from __future__ import annotations

import numpy as np


class AdaptiveResampler:
    """Stateful linear resampler with a tightly bounded drift correction."""

    def __init__(self, source_rate: int, target_rate: int) -> None:
        self.source_rate = source_rate
        self.target_rate = target_rate
        self.correction_ppm = 0.0

    def set_correction(self, ppm: float) -> None:
        self.correction_ppm = max(-250.0, min(250.0, float(ppm)))

    @property
    def ratio(self) -> float:
        return (self.target_rate / self.source_rate) * (1.0 + self.correction_ppm / 1_000_000)

    def process(self, data: np.ndarray) -> np.ndarray:
        if len(data) < 2:
            return data.copy()
        count = max(1, round(len(data) * self.ratio))
        if count == len(data):
            return data.copy()
        old = np.arange(len(data), dtype=np.float64)
        new = np.linspace(0, len(data) - 1, count, dtype=np.float64)
        result = np.empty((count, data.shape[1]), dtype=np.float32)
        for channel in range(data.shape[1]):
            result[:, channel] = np.interp(new, old, data[:, channel])
        return result

    def process_to_length(self, data: np.ndarray, frames: int) -> np.ndarray:
        """Resample one block to an exact frame count for continuous render timing."""
        frames = max(1, int(frames))
        if len(data) < 2:
            return np.repeat(data[:1], frames, axis=0)
        if frames == len(data) and self.source_rate == self.target_rate:
            return data.copy()
        old = np.arange(len(data), dtype=np.float64)
        new = np.linspace(0, len(data) - 1, frames, dtype=np.float64)
        result = np.empty((frames, data.shape[1]), dtype=np.float32)
        for channel in range(data.shape[1]):
            result[:, channel] = np.interp(new, old, data[:, channel])
        return result
