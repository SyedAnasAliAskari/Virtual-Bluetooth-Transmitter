import numpy as np

from dualsync.core.ring_buffer import AudioRingBuffer


def test_fifo_and_padding():
    ring = AudioRingBuffer(10, 2)
    ring.write(np.ones((4, 2), np.float32))
    output = ring.read(6)
    np.testing.assert_array_equal(output[:4], 1)
    np.testing.assert_array_equal(output[4:], 0)
    assert ring.underruns == 1


def test_overflow_drops_oldest():
    ring = AudioRingBuffer(5, 2)
    ring.write(np.repeat(np.arange(8, dtype=np.float32)[:, None], 2, axis=1))
    output = ring.read(5)
    np.testing.assert_array_equal(output[:, 0], [3, 4, 5, 6, 7])
    assert ring.overflow_frames == 3
