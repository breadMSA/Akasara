"""Tests for the BrainFlow-backed ASE producer.

Everything here runs with no hardware: BrainFlow's SYNTHETIC_BOARD is a real
BrainFlow session through the real API, so the descriptor, clock, tier and
self-test clauses are exercised end to end.

Run:  python test_producer.py
"""

import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.normpath(os.path.join(HERE, "..", "..", "spec", "conformance"))
sys.path.insert(0, HERE)

passed, failed = [], []


def test(name):
    def deco(fn):
        try:
            fn()
        except AssertionError as e:
            failed.append((name, str(e)))
            print(f"  FAIL  {name}\n        {e}")
        except Exception as e:                                  # noqa: BLE001
            failed.append((name, repr(e)))
            print(f"  ERROR {name}\n        {e!r}")
        else:
            passed.append(name)
            print(f"  ok    {name}")
        return fn
    return deco


def check(*args):
    r = subprocess.run(["node", os.path.join(CONF, "check.mjs"), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.returncode, r.stdout + r.stderr


def capture(kind, seconds=8.0, board="SYNTHETIC_BOARD", **kw):
    """One real BrainFlow session, returned as the three artefacts a vendor ships."""
    import producer
    from brainflow.board_shim import BrainFlowInputParams

    b = producer.Board(board, BrainFlowInputParams(), kind=kind, **kw)
    with b as live:
        samples, stamps = live.read(seconds)
    scale = producer.full_scale(samples)
    frames = producer.build_frames(samples, stamps, b, scale, "s-test")
    cap = producer.build_capability(
        b, scale, [{"uri": "loopback://test", "encodings": ["json"],
                    "max_sustained_kbps": 2000}], len(frames))
    prof = producer.PROFILES[kind]
    import tdfeat
    st = tdfeat.selftest_output(b.channels, b.sample_rate_hz,
                               prof["window_ms"], prof["stride_ms"],
                               prof["transform"])
    return cap, frames, [round(float(v), 9) for v in st]


def run_suite(cap, frames, st):
    with tempfile.TemporaryDirectory() as tmp:
        cp = os.path.join(tmp, "capability.json")
        fp = os.path.join(tmp, "frames.jsonl")
        sp = os.path.join(tmp, "selftest.json")
        with open(cp, "w", encoding="utf-8") as fh:
            json.dump(cap, fh)
        with open(fp, "w", encoding="utf-8") as fh:
            for f in frames:
                fh.write(json.dumps(f) + "\n")
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        return check(cp, fp, sp)


# --------------------------------------------------------------- the claim
@test("a live BrainFlow session produces a CONFORMANT sEMG capture")
def _():
    cap, frames, st = capture("semg")
    code, out = run_suite(cap, frames, st)
    assert code == 0, f"suite reported failures:\n{out}"
    assert "CONFORMANT" in out


@test("a live BrainFlow session produces a CONFORMANT EEG capture")
def _():
    cap, frames, st = capture("eeg", seconds=12.0)
    code, out = run_suite(cap, frames, st)
    assert code == 0, f"suite reported failures:\n{out}"
    assert "PASS  R-4.2   montage ase.eeg.1020.v1" in out, (
        "a board that names every channel with a 10-20 site must get the standard "
        f"montage, not the opaque one:\n{out}")


@test("the T1 feature space is the SAME one apps/replay pins for the same signal")
def _():
    """The point of a third implementation. If this producer invented its own
    feature space, a BrainFlow board and a Ninapro capture could not be compared
    and R-5.4 would be pinning two unrelated things."""
    import producer
    assert producer.PROFILES["semg"]["space"](16) == "akasara.replay.semg16.tdfeat.v1"
    assert producer.PROFILES["eeg"]["space"](19) == "akasara.replay.eeg19.bandpower.v1"
    # And the layout claim must match the transform's actual output order.
    import tdfeat
    win = np.zeros((40, 2))
    win[:, 0] = 1.0                       # channel 0 hot, channel 1 silent
    v = tdfeat.tdfeat(win)
    assert len(v) == 4
    # feature-major means [rms(c0), rms(c1), wl(c0), wl(c1)] -> rms of c0 is v[0]
    assert v[0] > 0 and v[1] == 0, f"layout claim does not match tdfeat(): {v}"
    assert producer.PROFILES["semg"]["layout"] == "feature-major"


# ------------------------------------------------------------ the clock trap
@test("R-5.2: BrainFlow's Unix-epoch timestamps are NOT written as epoch ns")
def _():
    """The trap this producer exists to demonstrate. BrainFlow's timestamp channel
    is Unix seconds; the obvious conversion to nanoseconds is ~1.79e18, which is
    over 2^53 and therefore silently corrupted by JSON. R-5.2 forbids it in words;
    this checks the code obeys."""
    cap, frames, _ = capture("semg", seconds=6.0)
    assert cap["clock"]["mono_epoch"] == "session"
    worst = max(f["t_mono_ns"] for f in frames)
    assert worst <= 2 ** 53, f"t_mono_ns {worst} exceeds JSON's exact integer range"
    # A capture of a few seconds cannot legitimately have a huge monotonic value.
    assert worst < 60e9, f"t_mono_ns {worst} is not session-relative"
    # ...while t_wall_ms IS wall time, and is required because there is an RTC.
    assert cap["clock"]["rtc"] is True
    assert all(f["t_wall_ms"] > 1_700_000_000_000 for f in frames)


@test("R-5.3: seq comes off the stride grid, so frames are not renumbered")
def _():
    _, frames, _ = capture("semg", seconds=6.0)
    seqs = [f["seq"] for f in frames]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert seqs[0] == 0


# ------------------------------------------------------- the honest refusals
@test("an ambiguous board kind is refused, not guessed")
def _():
    """SYNTHETIC_BOARD publishes the same 16 indices as both EEG and EMG. Picking
    one would produce a conformant descriptor over the wrong transform."""
    import producer
    from brainflow.board_shim import BrainFlowInputParams
    try:
        producer.Board("SYNTHETIC_BOARD", BrainFlowInputParams())
    except SystemExit as e:
        assert "ambiguous" in str(e), str(e)
    else:
        raise AssertionError("an ambiguous board was silently assigned a kind")


@test("no board gets a T3 badge, because BrainFlow exposes no ADC scale")
def _():
    cap, _, _ = capture("semg", seconds=6.0)
    assert "t3" not in cap and "ase.t3" not in cap["profiles"], (
        "a T3 badge was claimed without adc_bits or lsb_per_unit (R-3.3.1)")
    assert "t2" in cap and "ase.t2" in cap["profiles"]


@test("R-3.3.1: the declared T2 chain is clipped to the board's own Nyquist")
def _():
    """The textbook sEMG band is 20-450 Hz. On a 250 Hz board 450 Hz is above
    Nyquist, so declaring it would describe a filter that cannot exist."""
    cap, _, _ = capture("semg", seconds=6.0)
    band = [f for f in cap["t2"]["filters"] if f["kind"] == "bandpass"][0]
    nyq = cap["signal"]["sample_rate_hz"] / 2
    assert band["hz_high"] < nyq, f"declared {band['hz_high']} Hz against Nyquist {nyq}"
    assert band["hz_low"] == 20.0


@test("a synthetic session is labelled as one and cannot pass as a capture")
def _():
    cap, _, _ = capture("semg", seconds=6.0)
    assert cap["akasara.source"] == "simulated"
    assert cap["akasara.brainflow_board"] == "SYNTHETIC_BOARD"


@test("full scale is a constant, so the transform does not become adaptive (R-5.5)")
def _():
    """A per-capture peak would make the exported feature per-user adaptive, which
    R-5.5 then requires the device to declare and offer a way out of. Rounding to
    a decade is what keeps two captures from the same board in the same space."""
    import producer
    a = producer.full_scale(np.array([[123.4, -98.0]]))
    b = producer.full_scale(np.array([[456.7, -12.0]]))
    assert a == b == 1000.0, f"{a} vs {b}"
    cap, _, _ = capture("semg", seconds=6.0)
    assert cap["t1"]["adaptive"] is False


@test("quality is measured: a dead flat channel does not report 1.0")
def _():
    """Appendix A / R-5.6. The failure this catches is a producer that reports
    perfect contact for a lead that is not connected."""
    import producer
    from brainflow.board_shim import BrainFlowInputParams
    b = producer.Board("SYNTHETIC_BOARD", BrainFlowInputParams(), kind="semg")
    n = int(b.sample_rate_hz * 3)
    samples = np.random.default_rng(0).normal(0, 50, size=(n, b.channels))
    samples[:, 0] = 7.0                                   # channel 0 is dead
    stamps = 1785000000.0 + np.arange(n) / b.sample_rate_hz
    frames = producer.build_frames(samples, stamps, b, 1000.0, "s-q")
    assert frames, "no frames produced"
    assert all(f["quality"][0] == 0.0 for f in frames), "a flat channel scored above 0"
    assert any(f["quality"][1] > 0.9 for f in frames), "a live channel scored low"


@test("--list-boards reports the fleet this file makes reachable")
def _():
    import producer
    from brainflow.board_shim import BoardShim, BoardIds
    n = 0
    for name in dir(BoardIds):
        if not name.endswith("_BOARD"):
            continue
        try:
            BoardShim.get_board_descr(getattr(BoardIds, name))
        except Exception:                                       # noqa: BLE001
            continue
        n += 1
    assert n >= 40, f"only {n} boards described; the reach claim rests on this"
    assert callable(producer.list_boards)


@test("a vendor fork of the BrainFlow API produces ASE, and says which SDK it was")
def _():
    """MindRove ships `mindrove`, a rename-level fork of BrainFlow's binding.

    Skipped rather than failed when it is not installed: the fork is an extra
    reach claim, not a dependency of this producer. What must never happen is a
    capture taken through one SDK describing itself as the other, so the two
    things asserted are that the run is conformant and that every identifying
    string in the descriptor names mindrove.
    """
    try:
        import mindrove.board_shim                              # noqa: F401
    except ImportError:
        return
    from producer import DOC_URL
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "mr")
        subprocess.run(
            [sys.executable, os.path.join(HERE, "producer.py"),
             "--sdk", "mindrove", "--board", "SYNTHETIC_BOARD",
             "--kind", "eeg", "--seconds", "6", "--out", out],
            check=True, capture_output=True)
        cap = json.load(open(os.path.join(out, "capability.json"), encoding="utf-8"))
        _, log = check(os.path.join(out, "capability.json"),
                       os.path.join(out, "frames.jsonl"),
                       os.path.join(out, "selftest.json"))
        assert "CONFORMANT" in log, log[-400:]
    assert cap["vendor"] == "akasara-mindrove", cap["vendor"]
    assert cap["firmware"].split("/")[1].startswith("mindrove-"), cap["firmware"]
    assert "akasara.mindrove_board" in cap
    # Documentation URLs point at this producer's own path in the repository,
    # which is apps/brainflow/ whichever SDK ran; everything else that says
    # brainflow would be a false claim about where the signal came from.
    blob = json.dumps({k: v for k, v in cap.items() if k != "documentation"})
    blob = blob.replace(DOC_URL, "")
    assert "brainflow" not in blob.lower(), "a MindRove capture named the wrong SDK"


if __name__ == "__main__":
    print(f"BrainFlow producer tests (no hardware required)\n")
    # Definitions above run at import time via the decorator.
    print(f"\n{len(passed)} passed, {len(failed)} failed")
    sys.exit(1 if failed else 0)
