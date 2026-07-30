#!/usr/bin/env python3
"""An ASE-0.1 T1 producer whose signal source is a recorded dataset.

Why this exists: before it, ASE-0.1 had exactly one implementation, on one
signal (a phone IMU), written by the spec's own author. "Signal-agnostic" was a
design claim with nothing behind it. This is a second implementation, in a
second language, on a second modality, reading the spec text rather than the
first implementation.

It is a replay, and says so everywhere it can: the descriptor carries
`akasara.source: "replay"`, a vendor and model that name the dataset, and a
`quality` whose documented proxy is stated as an upper bound. Nothing here
should be mistaken for a device, and nothing here needs to be -- everything
downstream of the samples (feature space, frame format, self-test, session
model, transport, descriptor) is the real thing, which is exactly what needed
testing.

    python replay.py --root <ninapro_db5 dir> --subject s1 --out out/db5-s1
    node ../../spec/conformance/check.mjs out/db5-s1/capability.json \
        out/db5-s1/frames.jsonl out/db5-s1/selftest.json
"""

import argparse
import json
import os

import numpy as np

import quality as qual
import sources
import tdfeat

PRODUCER_VERSION = "0.1.0"
DOC_URL = ("https://github.com/breadMSA/Akasara/blob/spec/ase-0.1/"
           "apps/replay/README.md")


def windows(n_samples, sample_rate_hz, window_ms, stride_ms):
    """Yield (seq, start, end). `seq` is derived from the stride grid since
    session start rather than incremented per emitted frame, so a frame that is
    never produced leaves a visible hole in `seq` instead of a silently closed
    one (R-5.3)."""
    w = int(round(window_ms * sample_rate_hz / 1000))
    s = int(round(stride_ms * sample_rate_hz / 1000))
    seq = 0
    start = 0
    while start + w <= n_samples:
        yield seq, start, start + w
        seq += 1
        start += s


def cue_of(labels, start, end, names):
    """Label a window only when the cue covers all of it. A window straddling a
    cue boundary is genuinely two things, and calling it one of them would be
    manufacturing a clean label the recording does not contain."""
    if labels is None:
        return None, None
    seg = labels[start:end]
    first = int(seg[0])
    if first == 0 or not np.all(seg == first):
        return None, None
    return first, names.get(first)


def build_frames(source, sessions, sample_rate_hz):
    frames = []
    ns_per_sample = 1e9 / sample_rate_hz
    quality_fn = qual.eeg_quality if source.kind == "eeg" else qual.semg_quality
    for sess in sessions:
        x = sess.samples
        for seq, start, end in windows(x.shape[0], sample_rate_hz,
                                       source.window_ms, source.stride_ms):
            win = x[start:end]
            values = source.transform(win, sample_rate_hz)
            q = quality_fn(win, sample_rate_hz, mains_hz=source.mains_hz)
            frame = {
                "tier": "t1",
                # R-5.2: the window's END, in an epoch that starts at session
                # start (R-4.3 forbids a Unix-epoch ns clock -- it does not fit
                # JSON's exact integer range).
                "t_mono_ns": int(round(end * ns_per_sample)),
                "session_id": sess.session_id,
                "seq": seq,
                "feature_space": source.feature_space,
                "values": [round(float(v), 6) for v in values],
                "quality": [round(float(v), 4) for v in q],
            }
            cue, cue_name = cue_of(sess.labels, start, end, sess.label_names)
            if cue is not None:
                frame["akasara.cue"] = cue
                frame["akasara.cue_name"] = cue_name
            frames.append(frame)
    return frames


def build_capability(source, transport, margin=None):
    dim = source.dim
    expected = tdfeat.selftest_output(
        source.channels, source.sample_rate_hz, source.window_ms,
        source.stride_ms, source.transform)
    cap = {
        "ase_version": "0.1",
        "vendor": "akasara-replay",
        "model": f"{source.dataset}-{source.subject}",
        "firmware": PRODUCER_VERSION,
        "akasara.source": "replay",
        "akasara.dataset": source.citation,
        "tiers": ["t1"],
        "profiles": [],
        "signal": {
            "kind": source.kind,
            "channels": source.channels,
            "sample_rate_hz": source.sample_rate_hz,
            "montage": source.montage(),
        },
        "t1": {
            "feature_space": source.feature_space,
            "dim": dim,
            # R-5.4.1. Both transforms here concatenate whole feature blocks —
            # [rms(all ch), wl(all ch)] and [delta(all ch), theta(all ch), ...] —
            # so every channel of one feature is contiguous. `apps/gate` computes
            # the same two time-domain features and interleaves them instead;
            # neither is more correct, which is why the field exists.
            "layout": "feature-major",
            "window_ms": source.window_ms,
            "stride_ms": source.stride_ms,
            "producer": "dsp",
            "adaptive": False,
            "documentation": DOC_URL,
            # A replay has no acquisition path, so there is no acquisition
            # latency to report. What is reported is the transform's own cost,
            # measured, so the number means something rather than flattering.
            "latency_typ_ms": source.latency_typ_ms,
            "latency_max_ms": source.latency_max_ms,
        },
        "clock": {
            # Timestamps are derived from sample indices at the recording's
            # nominal rate. There is no oscillator, so there is no drift to
            # declare -- and no wall clock either, so frames carry no t_wall_ms.
            "rtc": False,
            "mono_epoch": "session",
            "drift_ppm_max": 0,
            "akasara.clock_basis": "sample index at the dataset's nominal rate",
        },
        "selftest": {
            "input": "ase.selftest.v1",
            "expected": [round(float(v), 9) for v in expected],
            "tolerance": 1e-9,
        },
        "don_count": source.don_count,
        "transport": transport,
        "requires_account": False,
        "requires_network": False,
        "developer_gate": False,
        "terms": {
            "cross_user_processing_permitted": True,
            "url": DOC_URL,
        },
    }
    if margin is not None:
        cap["t1"]["cross_user_margin"] = margin
    return cap


def measure_transform_latency(source, reps=25):
    """Time the production transform on one window, so latency_max_ms is a
    measurement on this machine rather than a guess."""
    import time
    w = int(round(source.window_ms * source.sample_rate_hz / 1000))
    win = np.random.default_rng(0).normal(0, 0.1, size=(w, source.channels))
    source.transform(win, source.sample_rate_hz)         # warm
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        source.transform(win, source.sample_rate_hz)
        times.append((time.perf_counter() - t0) * 1000)
    return round(float(np.median(times)), 3), round(float(np.max(times)), 3)


def db5_source(root, subject):
    src = sources.Db5Source(root, subject)
    src.dataset = "ninapro-db5"
    src.citation = ("Pizzolato et al. 2017, Ninapro DB5 (double Myo, "
                    "10 intact subjects)")
    # DB5's three exercises were recorded in one sitting with one donning.
    src.don_count = 1
    src.window_ms, src.stride_ms = 200, 100
    src.transform = lambda win, fs: tdfeat.tdfeat(win)
    src.dim = tdfeat.feature_dim(src.channels)
    src.feature_space = f"akasara.replay.semg{src.channels}.tdfeat.v1"
    return src


def pdeeg_source(root, subject):
    src = sources.PdEegSource(root, subject)
    src.dataset = "ds007822"
    src.citation = ("ds007822, three-player prisoner's dilemma EEG "
                    "hyperscanning, 19 ch at 300 Hz")
    src.don_count = 1
    # 1000 ms of window is not a preference: the delta band is 1-4 Hz and a
    # shorter window cannot resolve it. bandpower() refuses rather than
    # returning a number for a band it cannot see.
    src.window_ms, src.stride_ms = 1000, 500
    src.transform = tdfeat.bandpower
    src.dim = tdfeat.bandpower_dim(src.channels)
    src.feature_space = f"akasara.replay.eeg{src.channels}.bandpower.v1"
    return src


BUILDERS = {"db5": db5_source, "pdeeg": pdeeg_source}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="dataset root")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dataset", default="db5", choices=sorted(BUILDERS))
    ap.add_argument("--max-seconds", type=float, default=None,
                    help="truncate each session, for a small capture")
    ap.add_argument("--margin", help="path to a cross_user_margin.json from align.py")
    ap.add_argument("--port", type=int, default=8765,
                    help="port serve.py will bind; goes in the transport descriptor")
    ap.add_argument("--transport-kbps", type=int, default=2000,
                    help="declared max_sustained_kbps for the loopback transport")
    args = ap.parse_args()

    src = BUILDERS[args.dataset](args.root, args.subject)
    src.latency_typ_ms, src.latency_max_ms = measure_transform_latency(src)

    sess = src.sessions()
    if args.max_seconds:
        n = int(args.max_seconds * src.sample_rate_hz)
        for s in sess:
            s.samples = s.samples[:n]
            if s.labels is not None:
                s.labels = s.labels[:n]

    frames = build_frames(src, sess, src.sample_rate_hz)

    dim = src.dim
    rate_hz = 1000.0 / src.stride_ms
    json_bytes = 110 + dim * 8
    need_kbps = json_bytes * rate_hz * 8 / 1000.0
    transport = [{
        "uri": f"ws://localhost:{args.port}",
        "encodings": ["json"],
        # `serve.py --measure` times the real socket; the declared figure is
        # floored an order of magnitude below it, because an inflated capacity
        # claim is the specific thing R-4.4 exists to stop.
        "max_sustained_kbps": args.transport_kbps,
    }]
    if need_kbps >= args.transport_kbps:
        raise SystemExit(
            f"declared transport cannot carry the live rate: {need_kbps:.0f} kbps needed")

    margin = None
    if args.margin:
        with open(args.margin, encoding="utf-8") as fh:
            margin = json.load(fh)

    cap = build_capability(src, transport, margin)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "capability.json"), "w", encoding="utf-8") as fh:
        json.dump(cap, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out, "frames.jsonl"), "w", encoding="utf-8") as fh:
        for f in frames:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    # The self-test OUTPUT is recomputed by invoking the transform, not copied
    # out of the descriptor. For a software-only producer the two share a code
    # path, so this catches a stale or hand-edited descriptor and nothing more
    # -- the genuinely independent check is against the reference generator in
    # `conformance/selftest.mjs`, which `test_conformance.py` runs.
    actual = tdfeat.selftest_output(
        src.channels, src.sample_rate_hz, src.window_ms, src.stride_ms,
        src.transform)
    with open(os.path.join(args.out, "selftest.json"), "w", encoding="utf-8") as fh:
        json.dump([round(float(v), 9) for v in actual], fh)

    cued = sum(1 for f in frames if "akasara.cue" in f)
    print(f"{args.out}: {len(frames)} T1 frames over {len(sess)} session(s), "
          f"dim {dim}, {cued} cue-labelled ({100*cued/max(1,len(frames)):.0f}%)")


if __name__ == "__main__":
    main()
