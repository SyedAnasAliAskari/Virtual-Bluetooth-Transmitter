import numpy as np

from dualsync.core.resampler import AdaptiveResampler


def test_resamples_stereo_to_target_rate():
    source = np.linspace(-1, 1, 480, dtype=np.float32)
    stereo = np.repeat(source[:, None], 2, axis=1)
    result = AdaptiveResampler(48000, 44100).process(stereo)
    assert result.shape == (441, 2)
    assert np.isclose(result[0, 0], -1)
    assert np.isclose(result[-1, 0], 1)


def test_drift_correction_is_bounded():
    resampler = AdaptiveResampler(48000, 48000)
    resampler.set_correction(9999)
    assert resampler.correction_ppm == 250


def test_resamples_to_exact_render_block_length():
    source = np.repeat(np.linspace(-1, 1, 479, dtype=np.float32)[:, None], 2, axis=1)
    result = AdaptiveResampler(48000, 48000).process_to_length(source, 480)
    assert result.shape == (480, 2)
    assert np.isclose(result[0, 0], -1)
    assert np.isclose(result[-1, 0], 1)
