# BrainFlow → ASE producer

**64 boards become ASE producers by running one file at them.**

BrainFlow is one acquisition API in front of the small-vendor biosignal fleet:
OpenBCI Cyton/Ganglion, Muse, Neurosity Crown, BrainBit, g.tec Unicorn, OYMotion
gForce (sEMG), Ant Neuro, Mentalab, EmotiBit, FreeEEG32, PiEEG, AAVAA. A device
that speaks BrainFlow does not need its vendor to write firmware to speak ASE —
it needs this module pointed at it.

It is also the **third independent implementation** of ASE-0.1:

| | language | signal | acquisition |
| --- | --- | --- | --- |
| `apps/gate` | JavaScript, browser | phone IMU | live sensor |
| `apps/replay` | Python | recorded sEMG, EEG | files on disk |
| **`apps/brainflow`** | **Python** | **whatever the board is** | **live, someone else's API** |

## No hardware required

BrainFlow ships `SYNTHETIC_BOARD` and `PLAYBACK_FILE_BOARD`. Both are real
BrainFlow sessions through the real API, so every clause about descriptors,
clocks, tiers, quality and self-tests runs end to end — only the electrodes are
absent. A synthetic session is labelled `"akasara.source": "simulated"` in the
descriptor and names the board it came from, so it can never be mistaken for a
capture.

```bash
pip install brainflow numpy scipy

python producer.py --list-boards
python producer.py --board SYNTHETIC_BOARD --kind eeg  --seconds 20 --out out/synth-eeg
python producer.py --board SYNTHETIC_BOARD --kind semg --seconds 20 --out out/synth-semg

# then the spec judges its own producer
node ../../spec/conformance/check.mjs out/synth-eeg/capability.json \
     out/synth-eeg/frames.jsonl out/synth-eeg/selftest.json

python test_producer.py        # 13 tests, no hardware
```

Measured 2026-07-30, BrainFlow 5.22.2, `SYNTHETIC_BOARD`:

| capture | frames | shape | result |
| --- | --- | --- | --- |
| `--kind eeg` | 22 | 16 ch @ 250 Hz, dim 80 | **CONFORMANT** — 19 pass, 0 fail, 1 warn |
| `--kind semg` | 79 | 16 ch @ 250 Hz, dim 32 | **CONFORMANT** — 19 pass, 0 fail, 2 warn |

The warnings are `clock.drift_ppm_max not declared` (BrainFlow does not expose
it, and R-4.3 would rather have a warning than a number nobody measured) and, on
the sEMG run, the opaque montage — see below.

## Vendor SDKs that are BrainFlow under another name

Some vendors ship their own Python package instead of upstreaming a board.
MindRove's `mindrove` is a rename-level fork of BrainFlow's binding — same
`BoardShim`, same `BoardIds`, same method signatures down to the `preset`
default, and its own `SYNTHETIC_BOARD`. `--sdk mindrove` swaps the import and
nothing else:

```bash
pip install mindrove
python producer.py --sdk mindrove --board SYNTHETIC_BOARD --kind eeg --seconds 20 --out out/mr-eeg
```

Measured 2026-08-01, `mindrove` 5.3.0, `SYNTHETIC_BOARD`: 16 ch @ 250 Hz, dim
80 — **CONFORMANT, 19 pass, 0 fail, 1 warn**, the same warning as above.

Every identifying string in the descriptor names the SDK that actually ran
(`vendor: akasara-mindrove`, `firmware: producer-0.1.0/mindrove-5.3.0`,
`akasara.mindrove_board`), and a test asserts the word *brainflow* never appears
in a MindRove capture. A synthetic session through a vendor's SDK is evidence
about the API, not about their hardware, and the file is not allowed to blur
those.

## Real hardware

```bash
python producer.py --board CYTON_BOARD      --serial-port COM3 --kind eeg --out out/cyton
python producer.py --board MUSE_2_BOARD     --mac-address <mac> --kind eeg --out out/muse
python producer.py --board GFORCE_PRO_BOARD --kind semg --out out/gforce
```

Nothing in the code is synthetic-specific. The author owns none of these boards,
which is the point: the producer is written against the published API and the
published board descriptors, so a vendor or a user with the hardware can confirm
or refute it in one command.

## It lands in the same feature space as `apps/replay`

This is the reason the module reuses `../replay/tdfeat.py` instead of inventing
its own transform:

```
db5   : akasara.replay.semg16.tdfeat.v1  dim 32  layout feature-major
bflow : akasara.replay.semg16.tdfeat.v1  dim 32  layout feature-major
```

A 16-channel BrainFlow sEMG board and a Ninapro DB5 subject produce vectors in
**the same pinned space with the same layout**, so `align.py` ingests them
together with no changes. Verified: pointed at a DB5 capture and a synthetic
BrainFlow capture, `align.py` agreed on the space and the layout and then refused
for the correct reason — the synthetic board has no cue labels, so there are no
shared gestures to align on. A refusal on the data, not on the format, is what
interop working looks like.

If the producer had defined a fourth feature space, R-5.4 would be pinning two
unrelated things and nothing would be comparable.

## Three things this producer refuses to state

Each one is a place where a plausible value was available and would have been
false. They are the substance of what implementing the tiers taught.

**1. No T3 badge, on any board.** T3 is "raw samples at ADC resolution and native
rate". BrainFlow returns **microvolts** for EEG channels — it has already applied
the board's gain — and exposes neither the ADC width nor an LSB scale through any
API. R-3.3.1 requires `adc_bits` and `lsb_per_unit`, so both would have to be
invented. A vendor building on this file for *their own* board knows those two
numbers and should fill them in; a generic BrainFlow producer does not.

**2. An ambiguous `signal.kind` stops the run.** BrainFlow's channel taxonomy is
not reliable enough to infer from, and the shipped descriptors prove it:
`SYNTHETIC_BOARD` lists the **same 16 indices** as both `eeg_channels` and
`emg_channels`, and `ANT_NEURO_EE_410_BOARD` — a clinical EEG amplifier —
reports 8 EMG channels and **zero** EEG ones. An inference here would be wrong in
both directions, and `signal.kind` selects the T1 transform, so a wrong guess
produces a fully conformant descriptor over the wrong arithmetic. The producer
asks instead.

**3. A montage is standard only if every channel is named.** BrainFlow reports
electrode **names**, never electrode **geometry**. Where a board names all its
channels with 10-20 sites (Cyton, Muse, Crown) the montage is `ase.eeg.1020.v1`
with real labels; otherwise it is `ase.opaque.v1` with a `geometry_id` per
R-4.2.1, plus any partial labels as a vendor extension. There is nothing to build
`positions` from for a wristband, and the reference is `unspecified-by-brainflow`
because BrainFlow does not report that either.

## The clock trap, which is why R-5.2 is worded the way it is

BrainFlow's timestamp channel is a **Unix epoch in seconds**. The obvious
conversion:

```python
t_mono_ns = int(row[ts] * 1e9)        # 1.785e18
```

is over 2^53, so it is **not exactly representable in JSON** and the low digits
are silently lost. R-5.2 forbids a Unix-epoch nanosecond clock for exactly this
reason and says so in the clause text; this is the live case. The producer
measures `t_mono_ns` from the first sample of the session and declares
`mono_epoch: session` to match, while `t_wall_ms` carries the real wall time —
which R-5.1 *requires* here, because BrainFlow's timestamps mean the host does
have an RTC.

It is worth being blunt about what this implies for a vendor: the naive line
compiles, runs, produces plausible-looking output, and is wrong. That is the
class of defect the whole specification is organised around.

## Full scale is a constant, not a fit

ASE §5.7 wants ±1.0 to be the acquisition system's own full-scale range, and
BrainFlow does not report it. Normalising by the observed peak per capture would
make the exported feature **per-user adaptive**, which R-5.5 then obliges the
device to declare and to offer a way out of. So the scale is decade-rounded from
the observed magnitude and held constant, which keeps two captures from the same
board in the same space. Same reasoning as `apps/replay`'s PD-EEG source, reached
independently here.

## Adoption note

Two of the boards behind this API belong to vendors already on the ASE watch
list — **OYMotion gForce** (consumer sEMG) and **OpenBCI** (open hardware, raw
data by default). For those, adopting ASE is not a firmware project: it is this
file plus a terms clause. That is the pitch, and it is why BrainFlow was the
highest-leverage third implementation rather than a fourth signal.
