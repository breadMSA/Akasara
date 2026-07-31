"""The T1 transform and the R-5.7 self-test input, written from the ASE-0.1
text rather than ported from `conformance/selftest.mjs`.

That is deliberate. A specification that only one implementation has ever read
has not been shown to be readable. Both halves here were implemented from
§5 and §5.7 of ASE-0.1.md alone; `selftest_matches_reference` in the test
suite then checks the result against the reference generator, so a divergence
between the prose and the reference implementation shows up as a failing test
instead of as a vendor's silent misreading.

The transform is the same formula the browser gate uses
(`akasara.imu.tdfeat.v1`): per channel, RMS and waveform length over the
analysis window, concatenated. It is fixed, non-adaptive, and has no per-user
state, so the self-test exercises the same code path the frames do — which is
the only thing that makes R-5.7 worth anything.
"""

import numpy as np

DURATION_S = 2.0


def tdfeat(window):
    """window: (T, C) in normalised full scale -> (2C,) feature vector.

    Layout is rms[0..C-1] then wl[0..C-1]. Waveform length is the mean absolute
    first difference, i.e. length-normalised, so the value does not move when
    the window length changes.
    """
    x = np.asarray(window, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError(f"window must be (T, C), got shape {x.shape}")
    rms = np.sqrt(np.mean(x ** 2, axis=0))
    wl = np.mean(np.abs(np.diff(x, axis=0)), axis=0) if x.shape[0] > 1 else np.zeros(x.shape[1])
    return np.concatenate([rms, wl])


def feature_dim(channels):
    return 2 * channels


BANDS = [(1, 4), (4, 8), (8, 13), (13, 30), (30, 45)]      # delta..gamma


def bandpower(window, sample_rate_hz, bands=BANDS):
    """window: (T, C) -> (5C,) log band power, laid out band-major.

    A genuinely different transform, not the same one with more channels. The
    point of carrying two is that R-5.4's pinning has to hold for a feature
    space whose arithmetic the consumer has never seen, and a producer that
    only ever ran one transform has not shown that.

    Band-major layout (all channels of delta, then all of theta, ...) so a
    consumer can collapse per-channel structure band by band -- the reduction
    R-11.5 asks a feature space to beat.
    """
    x = np.asarray(window, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError(f"window must be (T, C), got shape {x.shape}")
    n = x.shape[0]
    # Periodogram over the analysis window itself: the window IS the segment,
    # so there is nothing to average and no Welch overlap to choose. Hann taper,
    # one-sided, scaled to power spectral density.
    taper = np.hanning(n)
    scale = 1.0 / (sample_rate_hz * np.sum(taper ** 2))
    spec = np.abs(np.fft.rfft(x * taper[:, None], axis=0)) ** 2 * scale
    spec[1:-1] *= 2.0
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    out = []
    for lo, hi in bands:
        sel = (freqs >= lo) & (freqs < hi)
        if not sel.any():
            raise ValueError(
                f"band {lo}-{hi} Hz is unresolvable in a {n}-sample window at "
                f"{sample_rate_hz} Hz; lengthen the window rather than fake it")
        out.append(np.log(np.trapezoid(spec[sel], freqs[sel], axis=0) + 1e-12))
    return np.concatenate(out)


def bandpower_dim(channels, bands=BANDS):
    return len(bands) * channels


EVOKED_TAIL_MS = 800
EVOKED_STEP = 4


def evoked(window, sample_rate_hz, tail_ms=EVOKED_TAIL_MS, step=EVOKED_STEP):
    """window: (T, C) -> the last `tail_ms` of it, decimated by `step`,
    laid out feature-major: all channels at the first retained instant, then
    all channels at the next.

    A third transform, and the least clever one in the file on purpose. It
    computes nothing: it drops the head of the window and keeps every `step`-th
    sample. It is here because measuring the two EEG spaces against each other
    on THINGS-EEG2 showed the band-power vector carries about a third of the
    cross-person transfer this one does (2.2x chance against 5.8x, over the same
    people, cues and splits). R-11.5 asks whether a space beats its own
    degenerate reduction; it does not ask whether the space was worth choosing,
    and a producer can pass that badge comfortably while throwing most of the
    signal away. Carrying both spaces is how that stays visible instead of
    becoming a footnote.

    No filtering and no baseline correction: doing either here would make this
    the producer's opinion rather than the recording's samples, and §3's T2 is
    where an opinion belongs.
    """
    x = np.asarray(window, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError(f"window must be (T, C), got shape {x.shape}")
    n_tail = int(round(tail_ms * sample_rate_hz / 1000))
    if n_tail > x.shape[0]:
        raise ValueError(
            f"a {tail_ms} ms tail does not fit in a {x.shape[0]}-sample window "
            f"at {sample_rate_hz} Hz")
    return x[x.shape[0] - n_tail::step].reshape(-1)


def evoked_dim(channels, sample_rate_hz, tail_ms=EVOKED_TAIL_MS,
               step=EVOKED_STEP):
    n_tail = int(round(tail_ms * sample_rate_hz / 1000))
    return channels * len(range(0, n_tail, step))


# --------------------------------------------------------------- ase.selftest.v1

def _xorshift32(seed, n):
    """First n outputs of xorshift32 seeded with `seed`, scaled to [-1, 1].

    Written to the spec's wording: the shifts are 13 left, 17 right, 5 left,
    each result truncated to 32 bits, and the scaling divisor is 0xffffffff.
    Python ints are unbounded, so every step masks explicitly; a language whose
    ints wrap gets this for free and that difference is exactly the kind of
    thing R-5.7.2's tolerance exists to absorb.
    """
    mask = 0xFFFFFFFF
    x = seed & mask
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        x = (x ^ (x << 13)) & mask
        x = (x ^ (x >> 17)) & mask
        x = (x ^ (x << 5)) & mask
        out[i] = (x / 0xFFFFFFFF) * 2 - 1
    return out


def selftest_input(channels, sample_rate_hz):
    """ase.selftest.v1 — (T, C) normalised full scale, exactly 2.000 s.

        x[c][n] = 0.5*sin(2pi(20+7c)n/fs) + 0.2*sin(2pi(150+11c)n/fs)
                  + 0.05*r[c][n]

    with r[c] the first 2*fs outputs of xorshift32 seeded with c+1.
    """
    n = int(round(DURATION_S * sample_rate_hz))
    idx = np.arange(n, dtype=np.float64)
    cols = []
    for c in range(channels):
        r = _xorshift32(c + 1, n)
        cols.append(
            0.5 * np.sin(2 * np.pi * (20 + 7 * c) * idx / sample_rate_hz)
            + 0.2 * np.sin(2 * np.pi * (150 + 11 * c) * idx / sample_rate_hz)
            + 0.05 * r
        )
    return np.stack(cols, axis=1)


def selftest_output(channels, sample_rate_hz, window_ms, stride_ms, transform=None):
    """R-5.7.1: the T1 output of the LAST analysis window ending at or before
    t = 2.000 s. Not an average, and never the first window."""
    x = selftest_input(channels, sample_rate_hz)
    n = x.shape[0]
    w = int(round(window_ms * sample_rate_hz / 1000))
    s = int(round(stride_ms * sample_rate_hz / 1000))
    if w > n:
        raise ValueError("analysis window is longer than the 2 s self-test input")
    last_start = ((n - w) // s) * s
    win = x[last_start:last_start + w]
    if transform is None:
        return tdfeat(win)
    return transform(win, sample_rate_hz)
