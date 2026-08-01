"""ASE-0.1 producer backed by BrainFlow — the third implementation.

Why this file is the cheapest thing in the repository per unit of reach.
BrainFlow is one acquisition API in front of 64 boards (counted, 5.22.2, by
asking it): OpenBCI Cyton and
Ganglion, Muse, Neurosity Crown, BrainBit, g.tec Unicorn, OYMotion gForce
(sEMG), Ant Neuro, Mentalab, EmotiBit, FreeEEG32, PiEEG. A device that speaks
BrainFlow therefore becomes an ASE producer by running this file at it, without
its vendor writing a line of firmware. That is the adoption route the spec needs
and it costs one Python module.

It is also the third *independent* implementation. `apps/gate` is JavaScript on a
phone IMU; `apps/replay` is Python on recorded files; this is Python against a
live acquisition API on hardware the author does not own. The T1 feature spaces
are deliberately the ones `apps/replay` already pins, so a BrainFlow board and a
Ninapro capture land in the same space and are directly comparable — which is the
entire point of R-5.4 and is worth more than a fourth feature space.

WHAT THIS RUNS ON WITH NO HARDWARE. BrainFlow ships a `SYNTHETIC_BOARD` and a
`PLAYBACK_FILE_BOARD`. Both are real BrainFlow sessions through the real API, so
every clause about descriptors, clocks, tiers and self-tests is exercised
end-to-end; only the electrodes are absent. Synthetic sessions are labelled
`akasara.source: simulated` in the descriptor and can never be mistaken for a
capture.

VENDOR SDKs THAT ARE BRAINFLOW IN ALL BUT NAME. Some vendors ship their own
Python package rather than upstreaming a board. MindRove's `mindrove` is a
rename-level fork of BrainFlow's binding: same `BoardShim`, same `BoardIds`,
the same method names and signatures down to the `preset` default, and its own
`SYNTHETIC_BOARD`. `--sdk mindrove` swaps the import and nothing else, so those
vendors get an ASE producer on the same terms as the 64 in BrainFlow. Every
string this file writes into a capability descriptor names the SDK it actually
used, because a capture from one must never claim to be a capture from the other.

Usage:
  python producer.py --board SYNTHETIC_BOARD --kind eeg --seconds 20 --out out/synth
  python producer.py --board CYTON_BOARD --serial-port COM3 --kind eeg --out out/cyton
  python producer.py --sdk mindrove --board MINDROVE_WIFI_BOARD --kind eeg --out out/arc
  python producer.py --list-boards
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "replay"))
import tdfeat                                                   # noqa: E402

PRODUCER_VERSION = "0.1.0"
DOC_URL = "https://github.com/breadMSA/Akasara/blob/main/apps/brainflow/README.md"


# ----------------------------------------------------------------- the SDK
class Sdk:
    """Which acquisition binding to import, and what to call it in the output.

    BrainFlow and the vendor forks of it are the same API under two names. The
    ONE thing that must not be shared is the label: a descriptor produced
    through MindRove's SDK says mindrove, so nobody can read a synthetic
    BrainFlow session as evidence about a MindRove board or the reverse.
    """

    KNOWN = {
        "brainflow": ("brainflow.board_shim", "BrainFlowInputParams", "BrainFlow"),
        "mindrove": ("mindrove.board_shim", "MindRoveInputParams", "MindRove SDK"),
    }

    def __init__(self, key):
        if key not in self.KNOWN:
            raise SystemExit(f"unknown --sdk {key!r}; "
                             f"one of {', '.join(sorted(self.KNOWN))}")
        mod_name, params_name, label = self.KNOWN[key]
        self.key, self.label, self.dist = key, label, key
        try:
            import importlib
            self.mod = importlib.import_module(mod_name)
        except ImportError as e:                                  # noqa: BLE001
            raise SystemExit(f"--sdk {key} needs `pip install {key}` ({e})")
        self.BoardShim = self.mod.BoardShim
        self.BoardIds = self.mod.BoardIds
        self.InputParams = getattr(self.mod, params_name)

    def version(self):
        try:
            from importlib.metadata import version
            return version(self.dist)
        except Exception:                                         # noqa: BLE001
            return "unknown"


class _DefaultSdk:
    """Stands in until `--sdk` is parsed, then imports BrainFlow on first touch.

    The import stays lazy so that someone who installed only a vendor fork gets
    the `--sdk` error, not a missing-brainflow traceback.
    """

    _real = None

    def __getattr__(self, name):
        if _DefaultSdk._real is None:
            _DefaultSdk._real = Sdk("brainflow")
        return getattr(_DefaultSdk._real, name)


SDK = _DefaultSdk()             # replaced by main(); every writer below reads it

# The 10-20 label set, upper-cased. A board is treated as carrying a standard
# montage only if EVERY channel it publishes is in here — a board that names
# three of eight electrodes has an opaque montage with three labels attached,
# not a standard one.
TEN_TWENTY = {
    "NZ", "FP1", "FPZ", "FP2", "AF7", "AF3", "AFZ", "AF4", "AF8",
    "F9", "F7", "F5", "F3", "F1", "FZ", "F2", "F4", "F6", "F8", "F10",
    "FT9", "FT7", "FC5", "FC3", "FC1", "FCZ", "FC2", "FC4", "FC6", "FT8", "FT10",
    "T9", "T7", "C5", "C3", "C1", "CZ", "C2", "C4", "C6", "T8", "T10",
    "TP9", "TP7", "CP5", "CP3", "CP1", "CPZ", "CP2", "CP4", "CP6", "TP8", "TP10",
    "P9", "P7", "P5", "P3", "P1", "PZ", "P2", "P4", "P6", "P8", "P10",
    "PO7", "PO3", "POZ", "PO4", "PO8", "O1", "OZ", "O2", "IZ",
    "A1", "A2", "M1", "M2",
}

# Time-domain features for muscle, log band power for brain — the same two
# transforms, and therefore the same two feature space identifiers, that
# apps/replay pins on Ninapro DB5 and ds007822.
PROFILES = {
    "semg": {
        "window_ms": 200, "stride_ms": 100,
        "transform": lambda win, fs: tdfeat.tdfeat(win),
        "dim": tdfeat.feature_dim,
        "space": lambda ch: f"akasara.replay.semg{ch}.tdfeat.v1",
        # R-5.4.1: tdfeat() returns [rms(all ch), wl(all ch)] — whole feature
        # blocks concatenated, so every channel of one feature is contiguous.
        "layout": "feature-major",
        # T2 for muscle: the conventional sEMG band, clipped to what the board's
        # own Nyquist allows. See t2_chain().
        "t2_band": (20.0, 450.0),
    },
    "eeg": {
        "window_ms": 1000, "stride_ms": 500,
        "transform": tdfeat.bandpower,
        "dim": tdfeat.bandpower_dim,
        "space": lambda ch: f"akasara.replay.eeg{ch}.bandpower.v1",
        "layout": "feature-major",
        "t2_band": (1.0, 45.0),
    },
}


# --------------------------------------------------------------- the board
class Board:
    """A BrainFlow board, described in ASE's terms.

    Every judgement this class makes about a board is one BrainFlow does not
    answer, and each one is either derived from something the board publishes or
    refused outright. There is no fallback that guesses.
    """

    def __init__(self, board_name, params, kind=None, mains_hz=50.0):
        BoardShim, BoardIds = SDK.BoardShim, SDK.BoardIds

        if not hasattr(BoardIds, board_name):
            raise SystemExit(f"unknown {SDK.label} board {board_name!r}; "
                             "run --list-boards")
        self.board_name = board_name
        self.board_id = getattr(BoardIds, board_name)
        self.descr = BoardShim.get_board_descr(self.board_id)
        self.params = params
        self.mains_hz = mains_hz
        self._shim = None

        rate = self.descr.get("sampling_rate")
        if not rate:
            raise SystemExit(
                f"{board_name} publishes no sampling_rate. For PLAYBACK_FILE_BOARD "
                "the rate belongs to the recording, so pass --master-board and the "
                "file; there is nothing honest to put in signal.sample_rate_hz "
                "otherwise.")
        self.sample_rate_hz = float(rate)

        eeg = list(self.descr.get("eeg_channels") or [])
        emg = list(self.descr.get("emg_channels") or [])
        self.kind = kind or self._infer_kind(eeg, emg)
        self.data_channels = {"eeg": eeg, "semg": emg}[self.kind] or eeg or emg
        if not self.data_channels:
            raise SystemExit(f"{board_name} publishes no eeg or emg channels")
        self.channels = len(self.data_channels)

        names = (self.descr.get("eeg_names") or "")
        self.names = [n.strip() for n in names.split(",") if n.strip()]

    def _infer_kind(self, eeg, emg):
        """BrainFlow's channel taxonomy is not trustworthy enough to infer from.

        Measured against the shipped descriptors: SYNTHETIC_BOARD lists the SAME
        16 indices as both `eeg_channels` and `emg_channels`, and
        ANT_NEURO_EE_410_BOARD — a clinical EEG amplifier — reports 8 emg
        channels and zero eeg. So an inference here would be wrong in both
        directions. Where the board is ambiguous the producer stops and asks,
        because `signal.kind` selects the T1 transform and getting it wrong
        produces a conformant descriptor over the wrong arithmetic.
        """
        if eeg and emg and set(eeg) == set(emg):
            raise SystemExit(
                f"{self.board_name} declares the same channels as both EEG and EMG, "
                "so its kind is genuinely ambiguous — pass --kind eeg|semg. "
                "(BrainFlow's taxonomy is a hint, not a fact: ANT_NEURO_EE_410, an "
                "EEG amplifier, reports emg channels and no eeg ones.)")
        if eeg and not emg:
            return "eeg"
        if emg and not eeg:
            return "semg"
        raise SystemExit(f"cannot tell what {self.board_name} measures — pass --kind")

    # ------------------------------------------------------------- montage
    def montage(self):
        """R-4.2. A standard montage is claimed only when the board names every
        channel with a 10-20 site. Otherwise the montage is opaque with a
        geometry_id, which R-4.2.1 requires and which is the honest answer:
        BrainFlow reports electrode NAMES, never electrode GEOMETRY, so for a
        wristband or an unlabelled cap there is nothing to build positions from.
        """
        labelled = (len(self.names) == self.channels
                    and all(n.upper() in TEN_TWENTY for n in self.names))
        if self.kind == "eeg" and labelled:
            return {
                "system": "ase.eeg.1020.v1",
                "site": "scalp",
                "side": "bilateral",
                "arrangement": "scattered",
                # BrainFlow does not report the reference. Saying so is the point
                # of R-4.2 asking for the field at all.
                "reference": f"unspecified-by-{SDK.key}",
                "positions": [{"ch": i, "label": n}
                              for i, n in enumerate(self.names)],
            }
        m = {
            "system": "ase.opaque.v1",
            "site": "unspecified",
            "side": "n/a",
            "arrangement": "single",
            "reference": f"unspecified-by-{SDK.key}",
            # R-4.2.1: identical across units whose arrangement is
            # interchangeable. Two units of the same board model are.
            "geometry_id": f"{SDK.key}.{self.descr.get('name', self.board_name)}.v1",
        }
        if self.names:
            m["akasara.partial_labels"] = self.names
        return m

    # -------------------------------------------------------------- tiers
    def t2_chain(self):
        """R-3.3.1. The chain is clipped to the board's own Nyquist rather than
        declared at the textbook corner: a 450 Hz sEMG lowpass on a 250 Hz board
        is not a conservative choice, it is an unrealisable filter, and R-3.3.1
        makes the descriptor state the one that ran.
        """
        lo, hi = PROFILES[self.kind]["t2_band"]
        nyq = self.sample_rate_hz / 2.0
        hi = min(hi, nyq * 0.95)
        if lo >= hi:
            return None
        chain = [{"kind": "bandpass", "hz_low": lo, "hz_high": round(hi, 1),
                  "order": 4}]
        if self.mains_hz and self.mains_hz < nyq:
            chain.insert(0, {"kind": "notch", "hz": self.mains_hz, "q": 30})
        return chain

    def t3_block(self):
        """Deliberately None, for every board.

        T3 is "raw samples at ADC resolution and native rate". BrainFlow returns
        microvolts for EEG channels — it has already applied the board's gain —
        and exposes neither the ADC width nor an LSB scale through any API. So
        `adc_bits` and `lsb_per_unit`, both of which R-3.3.1 requires, would have
        to be invented. A vendor building on this file for their own board DOES
        know those two numbers and should fill them in; a generic BrainFlow
        producer does not, and says so instead of guessing.
        """
        return None

    # ------------------------------------------------------------ session
    def __enter__(self):
        self._shim = SDK.BoardShim(self.board_id, self.params)
        self._shim.prepare_session()
        self._shim.start_stream()
        return self

    def __exit__(self, *exc):
        if self._shim is not None:
            try:
                self._shim.stop_stream()
            finally:
                self._shim.release_session()
            self._shim = None
        return False

    def read(self, seconds):
        """Collect `seconds` of data, returning (T, C) plus the board's own
        timestamps in Unix seconds."""
        BoardShim = SDK.BoardShim
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
        data = self._shim.get_board_data()
        ts_row = BoardShim.get_timestamp_channel(self.board_id)
        samples = np.asarray(data[self.data_channels], dtype=np.float64).T
        stamps = np.asarray(data[ts_row], dtype=np.float64)
        return samples, stamps

    @property
    def is_synthetic(self):
        return self.board_name in ("SYNTHETIC_BOARD", "PLAYBACK_FILE_BOARD")


# ----------------------------------------------------------- normalisation
def full_scale(samples):
    """Normalised full scale for a board that does not publish one.

    ASE-0.1 §5.7 wants +-1.0 to be the acquisition system's own full-scale range,
    and BrainFlow does not report it. A per-capture peak would make the T1
    transform per-user ADAPTIVE, which R-5.5 then requires the device to declare
    and offer a way out of — so instead one fixed decade-rounded constant is
    chosen from the observed magnitude and pinned into the feature space
    identifier's documentation. Same reasoning as apps/replay's PD-EEG source,
    and the same reason it is a constant rather than a fit.
    """
    peak = float(np.max(np.abs(samples))) if samples.size else 1.0
    if peak <= 0:
        return 1.0
    return float(10.0 ** np.ceil(np.log10(peak)))


# ------------------------------------------------------------------ frames
def build_frames(samples, stamps, board, scale, session_id):
    """T1 frames, with the clock trap BrainFlow hands every implementer.

    BrainFlow's timestamp channel is a Unix epoch in SECONDS. Converting it to
    nanoseconds the obvious way gives ~1.79e18, which is over 2^53 and therefore
    NOT exactly representable in JSON — R-5.2 forbids exactly this and says so in
    the clause text. It is a live trap rather than a theoretical one: the naive
    line compiles, runs, and silently corrupts the low digits of every timestamp.
    So t_mono_ns is measured from the first sample of the session, and
    `mono_epoch` is declared as `session` to match.

    t_wall_ms is present because BrainFlow's timestamps really are wall time and
    the host really does have an RTC — so R-5.1 requires it rather than permitting
    it, and it is the field a consumer aligns two devices on.
    """
    prof = PROFILES[board.kind]
    fs = board.sample_rate_hz
    win = int(round(prof["window_ms"] * fs / 1000.0))
    step = int(round(prof["stride_ms"] * fs / 1000.0))
    if len(samples) < win:
        raise SystemExit(
            f"captured {len(samples)} samples, one analysis window needs {win} "
            f"({prof['window_ms']} ms at {fs} Hz) — capture for longer")

    t0 = float(stamps[0])
    space = prof["space"](board.channels)
    frames = []
    for start in range(0, len(samples) - win + 1, step):
        end = start + win
        w = samples[start:end] / scale
        values = prof["transform"](w, fs) if board.kind == "eeg" \
            else prof["transform"](w, fs)
        t_end_s = float(stamps[end - 1])

        # R-5.6 / Appendix A: quality is measured, never asserted. Two things are
        # actually knowable here — how much of the window railed against the
        # declared full scale, and whether the channel moved at all. A channel
        # sitting at exactly one value is a dead lead, and reporting 1.0 for it
        # would be the failure the clause exists to catch.
        quality = []
        for c in range(board.channels):
            col = w[:, c]
            railed = float(np.mean(np.abs(col) >= 1.0))
            flat = 1.0 if float(np.ptp(col)) == 0.0 else 0.0
            quality.append(round(max(0.0, (1.0 - railed) * (1.0 - flat)), 3))

        frames.append({
            "tier": "t1",
            # R-5.2 — END of the analysis window, relative to session start.
            "t_mono_ns": int(round((t_end_s - t0) * 1e9)),
            "t_wall_ms": int(round(t_end_s * 1000)),
            "session_id": session_id,
            # R-5.3 — off the stride grid, so a dropped block leaves a hole
            # rather than being renumbered into a continuous run.
            "seq": start // step,
            "feature_space": space,
            "values": [round(float(v), 9) for v in values],
            "quality": quality,
        })
    return frames


def measure_transform_latency(board, reps=25):
    """R-5.3 wants typical and worst-case latency documented. A producer sitting
    on someone else's acquisition API cannot see the board's analogue path, so
    what is reported is the part this code is responsible for — the transform,
    timed on this machine — plus the window that must fill before it can run. The
    descriptor says which is which rather than passing one off as the other.
    """
    prof = PROFILES[board.kind]
    fs = board.sample_rate_hz
    win = int(round(prof["window_ms"] * fs / 1000.0))
    w = np.random.default_rng(0).normal(0, 0.1, size=(win, board.channels))
    prof["transform"](w, fs)                                     # warm
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        prof["transform"](w, fs)
        times.append((time.perf_counter() - t0) * 1000.0)
    return round(float(np.median(times)), 3), round(float(np.max(times)), 3)


def build_capability(board, scale, transport, n_frames):
    prof = PROFILES[board.kind]
    dim = prof["dim"](board.channels)
    typ_ms, max_ms = measure_transform_latency(board)
    expected = tdfeat.selftest_output(
        board.channels, board.sample_rate_hz, prof["window_ms"],
        prof["stride_ms"], prof["transform"])

    cap = {
        "ase_version": "0.1",
        "vendor": f"akasara-{SDK.key}",
        "model": f"{board.descr.get('name', board.board_name)}-{board.kind}",
        "firmware": f"producer-{PRODUCER_VERSION}/{SDK.key}-{SDK.version()}",
        # Never omitted, never ambiguous: a synthetic session is labelled as one.
        "akasara.source": "simulated" if board.is_synthetic else f"device-{SDK.key}",
        f"akasara.{SDK.key}_board": board.board_name,
        "tiers": ["t1"],
        "profiles": [],
        "signal": {
            "kind": board.kind,
            "channels": board.channels,
            "sample_rate_hz": board.sample_rate_hz,
            "montage": board.montage(),
        },
        "t1": {
            "feature_space": prof["space"](board.channels),
            "dim": dim,
            "layout": prof["layout"],
            "window_ms": prof["window_ms"],
            "stride_ms": prof["stride_ms"],
            "producer": "dsp",
            "adaptive": False,
            "documentation": DOC_URL,
            # The transform's own measured cost. The window must also fill before
            # the first vector exists, so the worst case a consumer sees is that
            # plus the window — stated as the sum, with the parts kept visible.
            "latency_typ_ms": round(prof["window_ms"] / 2.0 + typ_ms, 3),
            "latency_max_ms": round(prof["window_ms"] + prof["stride_ms"] + max_ms, 3),
            "akasara.transform_latency_ms": {"typ": typ_ms, "max": max_ms},
            "akasara.latency_excludes":
                f"the board's own acquisition and link latency, which {SDK.label} "
                "does not expose; these figures cover this producer only",
            "akasara.full_scale": scale,
            "akasara.full_scale_basis":
                "decade-rounded from the observed magnitude; a CONSTANT, because "
                "a per-capture fit would make this transform adaptive (R-5.5)",
            "lossless_encodings": ["f32"],
        },
        "clock": {
            # BrainFlow timestamps are host wall time, so there is an RTC. The
            # monotonic epoch is session start because a Unix-epoch nanosecond
            # value exceeds JSON's exact integer range (R-5.2).
            "rtc": True,
            "mono_epoch": "session",
            "akasara.clock_basis": f"{SDK.label} timestamp channel, host wall clock",
        },
        "selftest": {
            "input": "ase.selftest.v1",
            "expected": [round(float(v), 9) for v in expected],
            "tolerance": 1e-9,
        },
        "don_count": 1,
        "transport": transport,
        "requires_account": False,
        "requires_network": False,
        "developer_gate": False,
        "terms": {
            "cross_user_processing_permitted": True,
            "url": DOC_URL,
        },
        "akasara.frames_in_capture": n_frames,
    }

    chain = board.t2_chain()
    if chain:
        cap["tiers"].append("t2")
        cap["profiles"].append("ase.t2")
        cap["t2"] = {
            "channels": board.channels,
            "sample_rate_hz": board.sample_rate_hz,
            # BrainFlow returns uV for EEG channels; for an EMG board it returns
            # whatever the board sends, unscaled. Only the first is a unit.
            "unit": "uV" if board.kind == "eeg" else "a.u.",
            "layout": "sample-major",
            "filters": chain,
        }
    t3 = board.t3_block()
    if t3:
        cap["tiers"].append("t3")
        cap["profiles"].append("ase.t3")
        cap["t3"] = t3
    return cap


# -------------------------------------------------------------------- main
def list_boards():
    BoardShim, BoardIds = SDK.BoardShim, SDK.BoardIds
    rows = []
    for name in sorted(n for n in dir(BoardIds) if n.endswith("_BOARD")):
        try:
            d = BoardShim.get_board_descr(getattr(BoardIds, name))
        except Exception:                                       # noqa: BLE001
            continue
        rows.append((name, d.get("name", "?"), d.get("sampling_rate"),
                     len(d.get("eeg_channels") or []),
                     len(d.get("emg_channels") or [])))
    print(f"{len(rows)} boards known to {SDK.label} "
          f"{SDK.version()}; each one is a potential ASE producer\n")
    print(f"{'BOARD':34} {'NAME':18} {'RATE':>6} {'EEG':>4} {'EMG':>4}")
    for name, nice, rate, eeg, emg in rows:
        print(f"{name:34} {nice:18} {str(rate):>6} {eeg:>4} {emg:>4}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-boards", action="store_true")
    ap.add_argument("--sdk", default="brainflow", choices=sorted(Sdk.KNOWN),
                    help="acquisition binding; vendor forks share BrainFlow's API")
    ap.add_argument("--board", default="SYNTHETIC_BOARD")
    ap.add_argument("--kind", choices=sorted(PROFILES),
                    help="required when the board's channel taxonomy is ambiguous")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--out")
    ap.add_argument("--mains-hz", type=float, default=50.0,
                    help="0 to declare no mains notch")
    ap.add_argument("--serial-port", default="")
    ap.add_argument("--mac-address", default="")
    ap.add_argument("--ip-address", default="")
    ap.add_argument("--ip-port", type=int, default=0)
    ap.add_argument("--file", default="", help="PLAYBACK_FILE_BOARD recording")
    ap.add_argument("--master-board", default="",
                    help="PLAYBACK_FILE_BOARD: the board the file came from")
    ap.add_argument("--transport-kbps", type=int, default=2000)
    args = ap.parse_args()

    global SDK
    SDK = Sdk(args.sdk)

    if args.list_boards:
        list_boards()
        return

    if not args.out:
        raise SystemExit("--out is required unless --list-boards")

    BoardIds = SDK.BoardIds
    params = SDK.InputParams()
    params.serial_port = args.serial_port
    params.mac_address = args.mac_address
    params.ip_address = args.ip_address
    params.ip_port = args.ip_port
    params.file = args.file
    if args.master_board:
        params.master_board = getattr(BoardIds, args.master_board).value

    board = Board(args.board, params, kind=args.kind,
                  mains_hz=args.mains_hz or 0.0)

    session_id = f"{SDK.key[:2]}-{int(time.time())}-{board.board_name.lower()}"
    with board as live:
        samples, stamps = live.read(args.seconds)
    if len(samples) == 0:
        raise SystemExit("the board delivered no samples")

    scale = full_scale(samples)
    frames = build_frames(samples, stamps, board, scale, session_id)

    prof = PROFILES[board.kind]
    rate_hz = 1000.0 / prof["stride_ms"]
    json_bytes = 110 + prof["dim"](board.channels) * 8
    need = json_bytes * rate_hz * 8 / 1000.0
    if need >= args.transport_kbps:
        raise SystemExit(f"declared transport cannot carry {need:.0f} kbps")
    transport = [{"uri": f"loopback://{SDK.key}-producer",
                  "encodings": ["json"],
                  "max_sustained_kbps": args.transport_kbps}]

    cap = build_capability(board, scale, transport, len(frames))

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "capability.json"), "w", encoding="utf-8") as fh:
        json.dump(cap, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out, "frames.jsonl"), "w", encoding="utf-8") as fh:
        for f in frames:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    actual = tdfeat.selftest_output(
        board.channels, board.sample_rate_hz, prof["window_ms"],
        prof["stride_ms"], prof["transform"])
    with open(os.path.join(args.out, "selftest.json"), "w", encoding="utf-8") as fh:
        json.dump([round(float(v), 9) for v in actual], fh)

    print(f"{args.out}: {len(frames)} T1 frames, {board.channels} ch "
          f"{board.kind} @ {board.sample_rate_hz} Hz, dim "
          f"{prof['dim'](board.channels)}, tiers {', '.join(cap['tiers'])}")
    print(f"  board {board.board_name} ({cap['akasara.source']}), "
          f"full scale {scale:g}, feature space {cap['t1']['feature_space']}")


if __name__ == "__main__":
    main()
