from __future__ import annotations

import time
from collections import deque


class DriftController:
    """Slow PI controller that keeps a renderer near its target buffer depth."""

    def __init__(self, target_frames: int) -> None:
        self.target = target_frames
        self.integral = 0.0
        self.history: deque[tuple[float, int]] = deque(maxlen=200)
        self.ppm = 0.0

    def update(self, buffered_frames: int) -> float:
        now = time.perf_counter()
        self.history.append((now, buffered_frames))
        error = buffered_frames - self.target
        self.integral = max(-self.target * 20, min(self.target * 20, self.integral + error))
        # Positive depth error consumes fractionally faster.
        self.ppm = max(-250.0, min(250.0, error * 0.025 + self.integral * 0.0002))
        return self.ppm

    @property
    def health(self) -> str:
        if not self.history:
            return "Unknown"
        depth = self.history[-1][1]
        if depth < self.target * 0.25:
            return "Low"
        if depth > self.target * 2.5:
            return "High"
        return "Healthy"
