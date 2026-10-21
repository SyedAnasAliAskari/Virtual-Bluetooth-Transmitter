from __future__ import annotations

import threading
from collections import deque

import numpy as np


class AudioRingBuffer:
    """Bounded SPSC-friendly frame buffer; overflow drops oldest audio."""

    def __init__(self, capacity_frames: int, channels: int = 2) -> None:
        self.capacity = capacity_frames
        self.channels = channels
        self._chunks: deque[np.ndarray] = deque()
        self._frames = 0
        self._lock = threading.Lock()
        self.overflow_frames = 0
        self.underruns = 0

    @property
    def frames(self) -> int:
        with self._lock:
            return self._frames

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._frames = 0

    def write(self, data: np.ndarray) -> None:
        block = np.ascontiguousarray(data, dtype=np.float32)
        if block.ndim != 2 or block.shape[1] != self.channels:
            raise ValueError(f"expected (frames, {self.channels}) float audio")
        with self._lock:
            self._chunks.append(block.copy())
            self._frames += len(block)
            while self._frames > self.capacity and self._chunks:
                excess = self._frames - self.capacity
                first = self._chunks[0]
                if len(first) <= excess:
                    self._chunks.popleft()
                    self._frames -= len(first)
                    self.overflow_frames += len(first)
                else:
                    self._chunks[0] = first[excess:]
                    self._frames -= excess
                    self.overflow_frames += excess

    def read(self, frames: int, pad: bool = True) -> np.ndarray:
        output = np.zeros((frames, self.channels), dtype=np.float32)
        copied = 0
        with self._lock:
            while copied < frames and self._chunks:
                chunk = self._chunks[0]
                take = min(frames - copied, len(chunk))
                output[copied : copied + take] = chunk[:take]
                copied += take
                self._frames -= take
                if take == len(chunk):
                    self._chunks.popleft()
                else:
                    self._chunks[0] = chunk[take:]
            if copied < frames:
                self.underruns += 1
        return output if pad or copied == frames else output[:copied]
