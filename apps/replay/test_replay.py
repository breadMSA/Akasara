#!/usr/bin/env python3
"""Tests for the replay producer. Plain asserts, no test framework.

    python test_replay.py [--root <ninapro_db5 dir>]

The dataset tests skip without --root, because the recording is not in this
repository and never will be. Everything that does not need samples — the
self-test agreeing with the reference generator, the frame contract, the
transport — runs anywhere.
"""

import argparse
import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading

import numpy as np

import replay
import serve
import tdfeat

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.normpath(os.path.join(HERE, "..", "..", "spec", "conformance"))
VECTORS = os.path.join(CONF, "vectors")

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
    r = subprocess.run([node(), os.path.join(CONF, "check.mjs"), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def node():
    return "node"


# ----------------------------------------------------------- the spec text
@test("ase.selftest.v1 built from the spec text matches the reference generator")
def _():
    channels, fs = 16, 200.0
    r = subprocess.run([node(), os.path.join(CONF, "selftest.mjs"),
                        str(channels), str(int(fs))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    ref = np.array(json.loads(r.stdout)).T              # [ch][n] -> (n, ch)
    ours = tdfeat.selftest_input(channels, fs)
    assert ref.shape == ours.shape, f"{ref.shape} vs {ours.shape}"
    worst = float(np.max(np.abs(ref - ours)))
    # Both compute the same closed form in IEEE double; the only room for
    # disagreement is the PRNG's integer width, which is why this is tight.
    assert worst < 1e-12, f"independent implementations differ by {worst:.3e}"


@test("R-5.7.1: the published vector is the LAST window, not the first")
def _():
    channels, fs = 4, 200.0
    x = tdfeat.selftest_input(channels, fs)
    out = tdfeat.selftest_output(channels, fs, 200, 100)
    first = tdfeat.tdfeat(x[:40])
    last_start = ((x.shape[0] - 40) // 20) * 20
    last = tdfeat.tdfeat(x[last_start:last_start + 40])
    assert np.allclose(out, last), "not the last window"
    assert not np.allclose(out, first), "last window coincides with the first"


@test("the transform has no per-user state: same window in, same vector out")
def _():
    rng = np.random.default_rng(7)
    w = rng.normal(0, 0.3, size=(40, 8))
    a = tdfeat.tdfeat(w)
    tdfeat.tdfeat(rng.normal(0, 9.0, size=(40, 8)))     # a wildly different one
    b = tdfeat.tdfeat(w)
    assert np.array_equal(a, b), "transform output depends on what it saw before"


# ------------------------------------------------------------ frame contract
@test("R-5.3: seq comes off the stride grid, so a dropped window leaves a hole")
def _():
    grid = list(replay.windows(1000, 200.0, 200, 100))
    seqs = [s for s, _, _ in grid]
    assert seqs == list(range(len(seqs)))
    kept = [g for g in grid if g[0] % 3 != 1]           # drop every third window
    kept_seqs = [s for s, _, _ in kept]
    assert kept_seqs != list(range(len(kept_seqs))), \
        "dropping frames renumbered the sequence instead of leaving a gap"


@test("a window straddling a cue boundary is left unlabelled, not guessed")
def _():
    labels = np.array([0] * 10 + [5] * 10)
    names = {5: "five"}
    assert replay.cue_of(labels, 10, 20, names) == (5, "five")
    assert replay.cue_of(labels, 5, 15, names) == (None, None)
    assert replay.cue_of(labels, 0, 10, names) == (None, None)


@test("Appendix A quality: mains contamination and railing both push it down")
def _():
    fs, n = 200.0, 40
    t = np.arange(n) / fs
    clean = 0.2 * np.sin(2 * np.pi * 60 * t)
    line = 0.2 * np.sin(2 * np.pi * 50 * t)
    railed = np.sign(np.sin(2 * np.pi * 60 * t)) * 1.0
    import quality
    q = quality.semg_quality(np.stack([clean, line, railed], axis=1), fs, mains_hz=50.0)
    assert q[0] > 0.9, f"clean channel scored {q[0]:.3f}"
    assert q[1] < 0.1, f"mains-dominated channel scored {q[1]:.3f}"
    assert q[2] < q[0], f"railed channel {q[2]:.3f} not below clean {q[0]:.3f}"


# ---------------------------------------------------------- the suite itself
@test("R-5.2 is per session: a multi-session capture with session epochs passes")
def _():
    code, out = check(os.path.join(VECTORS, "good-sessions.capability.json"),
                      os.path.join(VECTORS, "good-sessions.frames.jsonl"))
    assert code == 0, f"multi-session vector rejected:\n{out}"


@test("R-5.2 still bites: a clock going backwards inside one session fails")
def _():
    code, out = check(os.path.join(VECTORS, "good-sessions.capability.json"),
                      os.path.join(VECTORS, "bad-clock-backwards.frames.jsonl"))
    assert code == 1, "backwards clock accepted"
    assert "FAIL  R-5.2" in out, f"failed for the wrong reason:\n{out}"


# ------------------------------------------------------------------ transport
def ws_client(port, timeout=5.0):
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    key = base64.b64encode(os.urandom(16))
    s.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
              b"Connection: Upgrade\r\nSec-WebSocket-Key: " + key +
              b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    assert b"101" in buf.split(b"\r\n")[0], buf[:80]
    return s


def ws_send(sock, obj):
    payload = json.dumps(obj).encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    n = len(payload)
    head = bytes([0x81])
    head += bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n)
    sock.sendall(head + mask + masked)


def ws_recv(sock):
    def exact(k):
        b = b""
        while len(b) < k:
            c = sock.recv(k - len(b))
            if not c:
                raise ConnectionError("closed")
            b += c
        return b
    b0, b1 = exact(2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", exact(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", exact(8))[0]
    return json.loads(exact(n).decode("utf-8"))


def with_server(capture_dir, fn, port=8799):
    cap = serve.Capture(capture_dir)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        try:
            if serve.handshake(conn):
                serve.serve_client(conn, cap, rate_limited=False)
        except (ConnectionError, OSError):
            pass
        finally:
            conn.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    try:
        return fn(port)
    finally:
        srv.close()
        t.join(timeout=2)


def tiny_capture(tmp):
    """A two-frame capture, so the transport tests do not need the dataset."""
    cap = json.load(open(os.path.join(VECTORS, "good-sessions.capability.json"),
                         encoding="utf-8"))
    os.makedirs(tmp, exist_ok=True)
    json.dump(cap, open(os.path.join(tmp, "capability.json"), "w", encoding="utf-8"))
    src = open(os.path.join(VECTORS, "good-sessions.frames.jsonl"), encoding="utf-8").read()
    open(os.path.join(tmp, "frames.jsonl"), "w", encoding="utf-8").write(src)
    json.dump(cap["selftest"]["expected"],
              open(os.path.join(tmp, "selftest.json"), "w", encoding="utf-8"))
    return tmp


@test("10.3: capability is the first message on connect, then frames")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        d = tiny_capture(os.path.join(tmp, "cap"))

        def body(port):
            s = ws_client(port)
            try:
                first = ws_recv(s)
                assert first.get("ase_version") == "0.1", f"first message was {first}"
                second = ws_recv(s)
                assert second.get("tier") == "t1", f"second message was {second}"
            finally:
                s.close()
        with_server(d, body)


@test("10.4: status, selftest and time_echo round-trip over the same socket")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        d = tiny_capture(os.path.join(tmp, "cap"))

        def body(port):
            s = ws_client(port)
            try:
                ws_recv(s)                                   # capability
                ws_send(s, {"cmd": "time_echo", "token": "abc"})
                seen = None
                for _ in range(12):
                    msg = ws_recv(s)
                    if msg.get("cmd") == "time_echo":
                        seen = msg
                        break
                assert seen is not None, "no time_echo reply among the frames"
                assert seen["token"] == "abc"
                assert isinstance(seen["t_mono_ns"], int) and seen["t_mono_ns"] > 0
            finally:
                s.close()
        with_server(d, body)


@test("a control command the replay cannot honour is refused with a reason")
def _():
    cap = serve.Capture(tiny_capture(os.path.join(tempfile.mkdtemp(), "cap")))
    r = cap.control({"cmd": "set_adaptive", "value": True})
    assert "error" in r and "adaptive" in r["error"], r


# ---------------------------------------------------------------------- ABF
ABF_FRAME = {
    "tier": "t1", "t_mono_ns": 1234567890123, "t_wall_ms": 1785000000000,
    "session_id": "s-1", "seq": 42, "feature_space": "x.v1",
    "values": [0.5, -0.25, 0.125, 1.0, -1.0, 0.0, 3.5, -0.0078125],
    "quality": [0.9, 0.8, 0.7, 1.0],
    "anchor": {"t_stim_mono_ns": 1234567000000, "timing_err_ms": 3.25},
}


def node_abf(direction, payload_hex_or_json, venc, channels):
    """Round-trip through conformance/abf.mjs so the two implementations are
    checked against each other rather than each against itself."""
    from pathlib import Path
    abf_url = Path(os.path.join(CONF, "abf.mjs")).as_uri()
    script = f'''
import {{ encodeT1, decodeT1 }} from {json.dumps(abf_url)};
const arg = process.argv[2];
if ({json.dumps(direction)} === "encode") {{
  const buf = encodeT1(JSON.parse(arg), {{ venc: {json.dumps(venc)}, channels: {channels} }});
  console.log(buf.toString("hex"));
}} else {{
  const out = decodeT1(Buffer.from(arg, "hex"), {channels});
  console.log(JSON.stringify(out));
}}
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "abfbridge.mjs")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(script)
        r = subprocess.run([node(), path, payload_hex_or_json],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    if r.returncode != 0:
        raise AssertionError("node bridge failed: " + r.stdout + r.stderr)
    return r.stdout.strip()


@test("ABF: bytes written here decode identically in the reference codec")
def _():
    import abf
    for venc in ("f32", "f16", "i16"):
        ours = abf.encode_t1(ABF_FRAME, venc=venc).hex()
        theirs = node_abf("encode", json.dumps(ABF_FRAME), venc, 4)
        assert ours == theirs, (
            f"{venc}: the two implementations disagree byte-for-byte\n"
            f"  py {ours}\n  js {theirs}")


@test("ABF: the reference codec's bytes decode identically here")
def _():
    import abf
    for venc in ("f32", "f16", "i16"):
        theirs_hex = node_abf("encode", json.dumps(ABF_FRAME), venc, 4)
        mine = abf.decode_t1(bytes.fromhex(theirs_hex), channels=4)
        js = json.loads(node_abf("decode", theirs_hex, venc, 4))
        assert mine["seq"] == js["seq"] and mine["t_mono_ns"] == js["t_mono_ns"]
        assert mine["_bytes"] == js["_bytes"], "trailer accounting differs"
        worst = max(abs(a - b) for a, b in zip(mine["values"], js["values"]))
        assert worst == 0.0, f"{venc}: decoded values differ by {worst}"


@test("ABF: f32 is exact, and the narrow encodings stay inside R-9.1 territory")
def _():
    import abf
    exact = abf.decode_t1(abf.encode_t1(ABF_FRAME, venc="f32"), 4)
    assert exact["values"] == ABF_FRAME["values"], "f32 round-trip is not exact"
    for venc, tol in (("f16", 1e-3), ("i16", 1e-3)):
        got = abf.decode_t1(abf.encode_t1(ABF_FRAME, venc=venc), 4)
        worst = max(abs(a - b) for a, b in zip(got["values"], ABF_FRAME["values"]))
        assert worst < tol, f"{venc} worst |delta| {worst:.3e}"


@test("ABF: R-9.4 fixed-point rounding is half AWAY from zero, on both sides")
def _():
    import abf
    # 0.7 * 255 = 178.5 exactly. Half-to-even gives 178, half-away gives 179.
    # The two reference implementations disagreed here until R-9.4 was written;
    # this test is the thing that keeps them agreeing.
    frame = {"t_mono_ns": 1, "seq": 0, "values": [0.0],
             "quality": [0.7, 0.3, 0.9, 0.1]}
    ours = abf.encode_t1(frame, venc="f32")
    trailer = list(ours[abf.HEADER_BYTES + 4:abf.HEADER_BYTES + 8])
    assert trailer == [179, 77, 230, 26], f"got {trailer}"
    theirs = bytes.fromhex(node_abf("encode", json.dumps(frame), "f32", 4))
    assert ours == theirs, "the two implementations round differently again"


@test("ABF: the S10 bandwidth table is what the codec actually produces")
def _():
    import abf
    kbps = lambda dim, hz, venc: abf.frame_bytes(dim, venc) * hz * 8 / 1000
    assert round(kbps(64, 50, "f32")) == 112
    assert round(kbps(64, 50, "f16")) == 61
    assert round(kbps(32, 20, "f32")) == 24


@test("R-5.4.1: an opaque vector cannot also state a cross-user margin")
def _():
    code, out = check(os.path.join(VECTORS, "bad-opaque-margin.capability.json"),
                      os.path.join(VECTORS, "bad-opaque-margin.frames.jsonl"))
    assert code == 1, "opaque layout accepted alongside a stated margin"
    assert "FAIL  R-5.4.1" in out, f"failed for the wrong reason:\n{out}"


@test("R-5.4.1: a descriptor with no t1.layout is not conformant")
def _():
    with open(os.path.join(VECTORS, "good.capability.json"), encoding="utf-8") as fh:
        cap = json.load(fh)
    assert cap["t1"]["layout"] == "feature-major"
    del cap["t1"]["layout"]
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "capability.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(cap, fh)
        code, out = check(p, os.path.join(VECTORS, "good.frames.jsonl"))
    assert code == 1 and "FAIL  R-5.4.1" in out, out


@test("align: the R-11.5 baseline collapses channels, not feature types")
def _():
    import align
    # Two channels, two feature types, values chosen so a correct reduction and
    # a wrong one cannot give the same answer: feature A is 0 on every channel,
    # feature B is 1 on every channel.
    fm = np.array([[0.0, 0.0, 1.0, 1.0]])          # A0 A1 B0 B1
    cm = np.array([[0.0, 1.0, 0.0, 1.0]])          # A0 B0 A1 B1
    want = np.array([[0.0, 1.0]])
    for X, layout in ((fm, "feature-major"), (cm, "channel-major")):
        got = align.channel_mean_reduction(X, 2, layout)
        assert np.allclose(got, want), f"{layout}: {got}"
    # and the layouts really are different, so keying off the space id matters
    assert not np.allclose(
        align.channel_mean_reduction(cm, 2, "feature-major"), want)


@test("align: every feature space either has a known layout or is refused")
def _():
    import align
    for path, expect in (("db5-s1", "feature-major"),
                         ("pd-G01S01", "feature-major")):
        p = os.path.join(HERE, "out", path, "capability.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            space = json.load(fh)["t1"]["feature_space"]
        assert align.LAYOUTS.get(space) == expect, space
    # apps/gate lays the same two features out the other way round; the README
    # tells people to feed its captures to this tool, so the entry must be here
    assert align.LAYOUTS["akasara.imu.tdfeat.v1"] == "channel-major"


# ----------------------------------------------------------------- dataset
def eeg_tests(root):
    @test("a second MODALITY produces a CONFORMANT capture: 10-20 EEG, band power")
    def _():
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "eeg")
            subprocess.run([sys.executable, os.path.join(HERE, "replay.py"),
                            "--dataset", "pdeeg", "--root", root,
                            "--subject", "sub-G01S01", "--out", out],
                           check=True, capture_output=True, encoding="utf-8",
                           errors="replace", cwd=HERE)
            code, log = check(os.path.join(out, "capability.json"),
                              os.path.join(out, "frames.jsonl"),
                              os.path.join(out, "selftest.json"))
            assert code == 0, log
            assert "WARN" not in log, "unexpected warning: " + log
            cap = json.load(open(os.path.join(out, "capability.json"), encoding="utf-8"))
            assert cap["signal"]["montage"]["system"] == "ase.eeg.1020.v1"
            assert cap["t1"]["feature_space"] != "akasara.replay.semg16.tdfeat.v1", (
                "R-5.4: a different transform must be a different pinned space")

    @test("bandpower refuses a window too short to resolve the band it claims")
    def _():
        # 200 ms at 300 Hz cannot see 1-4 Hz. Returning a number anyway would be
        # the quiet kind of wrong; it raises instead.
        short = np.zeros((60, 4))
        try:
            tdfeat.bandpower(short, 300.0)
        except ValueError as e:
            assert "unresolvable" in str(e), str(e)
        else:
            raise AssertionError("a 60-sample window claimed to resolve the delta band")


def dataset_tests(root):
    @test("a real DB5 subject produces a CONFORMANT capture")
    def _():
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "s1")
            subprocess.run([sys.executable, os.path.join(HERE, "replay.py"),
                            "--root", root, "--subject", "s1", "--out", out,
                            "--max-seconds", "30"],
                           check=True, capture_output=True, encoding="utf-8", errors="replace", cwd=HERE)
            code, log = check(os.path.join(out, "capability.json"),
                              os.path.join(out, "frames.jsonl"),
                              os.path.join(out, "selftest.json"))
            assert code == 0, log
            assert "WARN" not in log, f"unexpected warning:\n{log}"

    @test("the montage is real: 16 declared positions, two bands, right forearm")
    def _():
        src = replay.db5_source(root, "s1")
        m = src.montage()
        assert m["system"] == "ase.limb.v1"
        assert len(m["positions"]) == 16
        angles = sorted({p["angle_deg"] for p in m["positions"]})
        assert len(angles) == 16, f"bands not offset: {angles}"
        axial = sorted({p["axial_mm"] for p in m["positions"]})
        assert len(axial) == 2, f"expected two bands, got axial {axial}"
        assert m["akasara.spacing_mm"] > 0

    @test("samples are passed through, not re-scaled per subject")
    def _():
        src = replay.db5_source(root, "s1")
        s = src.sessions()[0]
        peak = float(np.max(np.abs(s.samples)))
        assert peak <= 1.0 + 1e-9, f"normalised full scale exceeded: {peak}"
        assert peak > 0.5, f"suspiciously quiet, check the scaling: {peak}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="ninapro_db5 directory; dataset tests skip without it")
    ap.add_argument("--eeg-root", help="ds007822 directory; EEG tests skip without it")
    args = ap.parse_args()
    if args.root and os.path.isdir(args.root):
        dataset_tests(args.root)
    else:
        print("  skip  DB5 tests (no --root)")
    if args.eeg_root and os.path.isdir(args.eeg_root):
        eeg_tests(args.eeg_root)
    else:
        print("  skip  EEG tests (no --eeg-root)")
    print(f"\n{len(passed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


