"""Appendix A `quality`, for a source that is a recording rather than a device.

Appendix A is normative and asks for electrode-skin impedance "where
measurable, otherwise a documented proxy", with power-line contamination folded
in. A replayed dataset has no impedance channel and never will, so this file is
the documented proxy — and its limits are stated rather than hidden, because a
`quality` a consumer cannot interpret is worse than no `quality` at all.

The proxy captures two of the three failure modes:

  * railing / saturation — the fraction of the window at or beyond full scale;
  * power-line contamination — the share of in-band power sitting in the mains
    bin, which Appendix A names as the dominant contact failure in practice.

It does NOT capture electrode-skin impedance, which is the failure mode a real
device measures directly. So this number is an UPPER BOUND on the true quality
of the original recording: a well-shielded but badly-contacted electrode scores
high here and would score low on a device. Anything consuming these frames
should read them as "not visibly broken", not as "verified good".
"""

import numpy as np


def semg_quality(window, sample_rate_hz, mains_hz=50.0,
                 band=(20.0, 95.0), sat_level=0.98, line_fatal=0.5):
    """window: (T, C) normalised full scale -> (C,) quality in 0..1.

    q = (1 - min(1, line_share / line_fatal)) * (1 - saturated_fraction)

    `line_share` is mains-bin power over total power in the EMG band; at or
    above `line_fatal` the channel is treated as unusable. A channel with no
    in-band power at all is reported 0.0 — Appendix A's "open contact".
    """
    x = np.asarray(window, dtype=np.float64)
    n, c = x.shape

    sat = np.mean(np.abs(x) >= sat_level, axis=0)

    spec = np.abs(np.fft.rfft(x, axis=0)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    nyquist = sample_rate_hz / 2.0

    hi = min(band[1], nyquist)
    in_band = (freqs >= band[0]) & (freqs <= hi)
    band_power = spec[in_band].sum(axis=0)

    if mains_hz < nyquist:
        # one bin either side, so the estimate survives a slightly off-nominal
        # mains frequency at the coarse resolution a 200 ms window gives.
        step = freqs[1] - freqs[0] if len(freqs) > 1 else sample_rate_hz
        line_sel = np.abs(freqs - mains_hz) <= step
        line_power = spec[line_sel].sum(axis=0)
    else:
        # mains is above Nyquist: it has aliased somewhere unknowable, and
        # claiming a clean line share would be a fabrication.
        line_power = np.zeros(c)

    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(band_power > 0, line_power / np.maximum(band_power, 1e-30), 1.0)

    q = (1.0 - np.minimum(1.0, share / line_fatal)) * (1.0 - sat)
    q = np.where(band_power > 0, q, 0.0)
    return np.clip(q, 0.0, 1.0)


def eeg_quality(window, sample_rate_hz, mains_hz=50.0,
                band=(1.0, 45.0), sat_level=0.98, line_fatal=0.5):
    """Appendix A EEG: impedance plus railing/saturation over the window.

    Impedance is again unavailable from a recording, so the same proxy applies
    over the EEG band, with the same upper-bound caveat. Reported separately
    from `semg_quality` because the band and the mains relationship differ, not
    because the arithmetic does.
    """
    return semg_quality(window, sample_rate_hz, mains_hz=mains_hz, band=band,
                        sat_level=sat_level, line_fatal=line_fatal)
