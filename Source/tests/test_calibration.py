import numpy as np

from dualsync.core.latency_calibrator import estimate_arrival, make_chirp


def test_arrival_estimator_detects_known_delay():
    rate = 48000
    chirp = make_chirp(rate)
    delay = 3216
    recording = np.concatenate((np.zeros(delay, np.float32), chirp, np.zeros(2000, np.float32)))
    arrival_ms, confidence = estimate_arrival(recording, chirp, rate)
    assert abs(arrival_ms - delay * 1000 / rate) < 0.1
    assert confidence > 0.99
