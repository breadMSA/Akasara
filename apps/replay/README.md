# Replay

A second ASE-0.1 implementation, on purpose.

Before this, the spec had exactly one implementation: the browser gate in
`../gate`, on one signal (a phone IMU), written by the spec's own author, in the
same language as the conformance suite. "Signal-agnostic" was a design claim
with nothing behind it, and "another vendor could implement this" was an
assertion nobody had tested. This is the test: a producer in a **different
language**, on a **different modality**, written from the spec text rather than
from the first implementation.

It found one defect in the conformance suite and three in the specification text.
That is the point.

## What it is

`replay.py` turns a recorded dataset into a conformant ASE-0.1 T1 source:
`capability.json`, `frames.jsonl`, `selftest.json`, and a live
`ws://localhost` binding served by `serve.py`. Three datasets are wired up, and
they are deliberately unalike:

| | `--dataset db5` | `--dataset pdeeg` | `--dataset thingseeg2` |
| --- | --- | --- | --- |
| signal | 16-ch surface EMG, two Myo bands | 19-ch scalp EEG | 17-ch scalp EEG, posterior only |
| rate | 200 Hz | 300 Hz | 100 Hz |
| montage system | `ase.limb.v1` (geometry) | `ase.eeg.1020.v1` (labels) | `ase.eeg.1020.v1` (labels) |
| T1 transform | RMS + waveform length | log band power, 5 bands | band power, **or** the evoked window itself |
| dim | 32 | 95 | 85 / 340 |
| window / stride | 200 / 100 ms | 1000 / 500 ms | 1000 / 1000 ms |
| cue | the shared movement | the shared round | the shared image, 200 of them |
| adaptation | none | none | **frozen, per-user, upstream** |

Nothing but the sample buffer is common to the three paths. That is the point:
"signal-agnostic" had been tested on one signal.

It is a replay and never pretends otherwise. The descriptor carries
`akasara.source: "replay"`, a vendor of `akasara-replay`, a model naming the
dataset, and a `quality` whose proxy is documented as an upper bound. Nothing
here is a device. Nothing here needs to be: the sensor is the only part standing
in, and everything downstream of it — feature space, frame format, self-test,
session model, transport, descriptor, rights declarations — is the real thing,
which is what needed testing.

## Result

Both, checked by the suite in `../../spec/conformance`:

```
db5        s1                 CONFORMANT — 22 pass, 0 fail, 0 warn
pdeeg      sub-G01S01         CONFORMANT — 20 pass, 0 fail, 0 warn
thingseeg2 sub-01 bandpower   CONFORMANT — 21 pass, 0 fail, 0 warn   (after R-5.5.1)
thingseeg2 sub-01 evoked      CONFORMANT — 22 pass, 0 fail, 0 warn   (+ R-11.5 margin)
```

The parenthesis on the third line is the whole story of the third dataset: on
the spec as it stood, the only conformant descriptor available to it was a false
one. See below.

Zero warnings, where the browser gate has two permanent ones, and the reason is
instructive: the gate's warnings are *"opaque montage"* and *"undeclared clock
drift"*, and a replayed sEMG recording has neither problem. The montage is a
documented electrode geometry rather than a phone's unknowable internal one, and
timestamps come from sample indices at the recording's nominal rate, so there is
no oscillator and no drift to declare. Those two warnings were always about the
IMU, not about the spec.

## The defects it found

**One, in the suite: `t_mono_ns` monotonicity was capture-wide.**
`check.mjs` enforced `t_mono_ns` monotonicity across the whole capture. But
R-4.3 allows the monotonic epoch to be **session start**, and R-6.1 requires a
new session at every don — so a capture holding several sessions restarts the
clock at each one, legitimately. DB5 records its three exercises as three
separate acquisitions, which this producer exports as three sessions, and the
suite rejected the result.

The suite was wrong about the requirement; no requirement changed. Monotonicity
is now per `session_id`, and both directions are locked by vectors:
`good-sessions.*` must pass, `bad-clock-backwards.frames.jsonl` must still fail
R-5.2.

A single-implementation specification cannot find this out about itself. Every
capture the gate produces is one session, so the bug was unreachable from the
only code that had ever exercised the suite.

**Two, in the spec: §9.2 did not say how to round.** The ABF binary encoding has
two fixed-point quality fields. The JavaScript reference codec rounds with
`Math.round` — half away from zero. `abf.py`, written from the layout table
alone, used Python's default — half to even. On a quality of exactly 0.7 the
product is 178.5, and the two implementations emit **different bytes for the
same frame**: 178 against 179.

It cannot change a decision; it is below the field's own resolution. It can
absolutely burn an afternoon for the first vendor who diffs their firmware's
bytes against the reference and finds one byte off in a hundred. §9.2 now says
`floor(v × max + 0.5)` (**R-9.4**), and a test encodes on one side and decodes
on the other so the two stay pinned together.

This is the defect class a spec cannot find by being read carefully. Both
implementations were individually correct and self-consistent; only running them
against each other made the gap visible.

**Three, in the spec: R-5.4 pinned the transform but not the order of its
answer.** This producer lays out `[rms(all channels), wl(all channels)]`. The
gate computes the same two features and lays out `[rms(ch0), wl(ch0), rms(ch1),
…]`. Both conformant, both correct, mutually unusable — and the failure is
silent, because a consumer that collapses the wrong axis averages amplitude
together with waveform length and still produces a number. That number is the
channel-mean baseline §11.5 asks a vendor to beat, so the clause was asking for a
measurement nobody could reliably take. **R-5.4.1** now requires `t1.layout`:
`feature-major`, `channel-major`, or `opaque`. `opaque` is a legitimate answer
and costs the device its ability to state an R-11.5 margin, because for a vector
that does not factor into channels the baseline does not exist.

The first two defects came from one implementation reading the spec. This one
came from two of them being pointed at each other, which is a different and
cheaper instrument than a third reader.

**Four, in the spec: R-5.5 assumed the adaptation was yours to switch off.**
R-5.5 says that if exported T1 carries per-user adaptation, the device must
declare it, carry `adapt_state`, **and offer a non-adaptive mode**. THINGS-EEG2
ships samples that have already been whitened per participant — a matrix fitted
from that participant's own recording, applied to every epoch of it — and the
un-whitened stream is not distributed. So this producer's exported T1 *is*
per-user adaptive, and there is no switch anywhere for it to offer.

That left exactly two descriptors, and both were bad. Declare `adaptive: false`,
because the whitening was somebody else's decision: passes the suite, and is a
lie about what a consumer is holding. Declare `adaptive: true` truthfully: fails
R-5.5, for a reason the vendor cannot fix. A clause that fails honesty and
passes evasion is backwards.

**R-5.5.1** now covers the case: where the adaptation was fitted upstream and
frozen, the descriptor declares `adapt_scope: "frozen"`, `non_adaptive_mode:
false`, and `adapt_fitted_on` — a plain statement of what was fitted and on
whose data — and `adapt_state` must not move within a session, which the suite
checks. What a consumer loses is stated rather than hidden: two users' vectors
from such a device are related by an unknown per-user map even when
`feature_space` matches, so anything assuming a shared frame (a fixed threshold,
a template, a distance compared across people) is wrong; anything fitting a map
per user is not.

This is the first defect found by neither reading nor cross-implementation, but
by a *third dataset* whose acquisition path had a shape the spec had not
imagined. It is also the one most likely to matter commercially: every SDK that
exports features computed after an enrollment calibration is in exactly this
position, and under R-5.5 alone all of them would have declared `false`.

The self-serving reading is available and should be said out loud: the author of
the spec changed the spec so that his own capture would pass. The test of
whether that is what happened is whether the new clause lets anything through
that R-5.5 was trying to stop, and it does the reverse. Before it, a vendor
shipping enrollment-calibrated features could declare `adaptive: false` and
point at the absence of any true alternative; R-5.5.1 removes that excuse and
costs such a vendor three fields it did not have to write, one of them prose. It
adds an obligation and withdraws none. What it does not do — and this is the
part the clause cannot fix — is make a frozen-adaptive device as useful as a
non-adaptive one. It only makes the difference legible.

## Producing

```
python replay.py --root <ninapro_db5 dir> --subject s1 --out out/db5-s1
python replay.py --dataset pdeeg --root <ds007822 dir> \
    --subject sub-G01S01 --out out/pd-G01S01
python replay.py --dataset thingseeg2 --root <things-eeg2 dir> \
    --subject sub-01 --space evoked --out out/te2ev-sub-01
node ../../spec/conformance/check.mjs \
    out/db5-s1/capability.json out/db5-s1/frames.jsonl out/db5-s1/selftest.json
```

No dataset is in this repository and none will be. `out/` is ignored. The
THINGS-EEG2 root is a directory of `sub-NN_test.npy` files taken from the
preprocessed 17-channel release (OSF component `anp5v`) plus that project's
`image_metadata.npy`, which supplies the 200 cue names; only the **test**
partition is needed, about 209 MB of each subject's 1.07 GB archive.

## Serving — §10.3

```
python serve.py --capture out/db5-s1          # ws://localhost:8765
python serve.py --capture out/db5-s1 --measure
```

Hand-rolled RFC6455, no dependencies, bound to 127.0.0.1 only (R-10.5).
Capability is the first message on connect, then frames paced at the declared
stride, with the §10.4 control plane (`status`, `selftest`, `time_echo`) live on
the same socket. Commands a replay cannot honour — `set_tier`, `set_adaptive` —
are refused with a stated reason rather than ignored.

This exists because the descriptor declares a `ws://localhost` transport, and a
declared transport that nothing serves is a false claim. `--measure` times the
framing path so the declared `max_sustained_kbps` has a measurement behind it:
138,747 kbps measured on loopback, declared 2,000, against 50 kbps needed at the
live rate.

## Consuming — two people's frames, jointly

```
python align.py out/db5-s1 out/db5-s2 ... --out out/cross_user_margin.json
python align.py out/db5-s1 ... --null        # the control
```

`align.py` reads **only** `capability.json` and `frames.jsonl`. It never opens
the dataset and never sees any private state of the producer. If a cross-person
map can be fitted from that alone, the descriptor is carrying what it claims to.

It computes the one number R-11.5 asks a vendor to publish about itself — does
this feature space beat its own channel-mean reduction at calibration-free
cross-person retrieval — and writes it back into the descriptor:

| | P@1 | vs chance |
| --- | --- | --- |
| full feature space | 0.224 | 5.8x |
| channel-mean reduced | 0.062 | 1.6x |
| **margin** | **+0.162** | 95% CI [+0.153, +0.172] |

6 subjects, 30 ordered pairs, 26-way retrieval of held-out cues fitted on 26
disjoint ones, 20 random splits, 6/6 subjects positive. Chance 0.038.

**The control:** with the cue correspondence between people permuted, the full
space scores 0.036 against a chance of 0.038 (0.9x) and the margin collapses to
−0.004. Whatever the map is recovering, it is the shared movement.

### The EEG leg says something different, and it is a negative

Run the same measurement on the EEG captures, where the cue is the round of a
three-player game, and the margin is real but tiny — and then it survives the
control that matters:

| pairs | full P@1 | reduced | margin | 95% CI |
| --- | --- | --- | --- | --- |
| within a triad — people who played the same rounds | 0.078 (1.6x) | 0.068 | +0.010 | [+0.005, +0.015] |
| between triads — people who never shared a round | 0.070 (1.4x) | 0.061 | +0.010 | [+0.007, +0.012] |
| within, cue correspondence permuted | 0.048 (1.0x) | 0.052 | −0.004 | [−0.008, +0.001] |
| between, cue correspondence permuted | 0.050 (1.0x) | 0.050 | +0.001 | [−0.002, +0.003] |

18 subjects, 40 shared rounds, 20-way retrieval, chance 0.050.

Three things are true at once and they have to be kept apart.

The retrieval is **not** noise: 1.4–1.6x chance, and both permutation controls
sit flat on 1.0x. Something transfers.

The margin is **not** about the pair. Within and between are identical to three
decimals, and people in different triads never shared a round — they shared only
the position in the session. §11.5 warns that a margin can be earned from generic
transferable structure; this is that warning coming true in the extreme.

Asking the sharper question directly — does sharing the rounds raise the
retrieval at all, before any reduction — gives **+0.008, 95% CI [−0.001, +0.017],
Wilcoxon p = 0.099, 12/18 subjects positive.** A near-miss, reported as one. It
is not evidence of a pair effect and it is not evidence against one.

So the EEG captures publish **no** `cross_user_margin` at all. The number would
pass the suite — R-11.5 only checks that a stated margin is stated readably —
and it would be misleading, which is a good demonstration of what R-11.2 means
when it says the margin is measured on data the suite never sees.

**What this is not.** It is a negative about *this task*, not about EEG. The cue
is the round index, and forty rounds of the same game are forty repetitions of
one mental state, not forty distinct ones — unlike DB5, where the cues are
genuinely different movements. A 20-way retrieval over them has a ceiling near
the floor, and a task with no headroom cannot show a pair effect even where one
exists. Read it as: the descriptor carried enough for a second modality to be
consumed at all, and the honest reading of what came out was to publish nothing.

The DB5 result is not affected by this: its permutation control does collapse,
and a cross-group control does not apply because the shared movement is shared
by everyone by construction.

### The EEG negative, revisited on a task with headroom — and half of it was the transform

The paragraph above blames the *task*: forty rounds of one game are forty
repetitions of one state, so a 20-way retrieval over them has a ceiling near its
floor. That was right, and it was incomplete.

THINGS-EEG2 removes the ceiling by construction. Ten people view the **same 200
images**, 80 repetitions each, so the cues are 200 genuinely different states and
the correspondence between two people's cue *k* is the stimulus itself rather
than a shared clock. Same estimator as everywhere else here: calibration-free
A → B ridge map fitted on 100 cues, 100-way retrieval of the other 100, 20
splits, aggregated to the subject, bootstrapped over subjects, chance 0.010.

| T1 space | full P@1 | channel-mean | margin | 95% CI | subjects up |
| --- | --- | --- | --- | --- | --- |
| `eeg17.bandpower.v1` — log power, 5 bands | 0.020 (2.0x) | 0.019 (1.9x) | +0.000 | [−0.001, +0.002] | 6/10 |
| `eeg17.evoked800d4.v1` — the window itself | 0.069 (6.9x) | 0.029 (2.9x) | **+0.040** | [+0.036, +0.044] | **10/10** |
| bandpower, cue correspondence permuted | 0.010 (1.0x) | 0.010 (1.0x) | −0.000 | [−0.001, +0.000] | 4/10 |
| evoked, cue correspondence permuted | 0.010 (1.0x) | 0.010 (1.0x) | −0.000 | [−0.001, +0.000] | 4/10 |

Both controls sit flat on chance, so the second row is transfer and not an
artefact of the estimator.

So EEG does carry a cross-person margin, and the earlier negative was measuring
the transform as well as the task. Band power earns nothing here even with 200
distinct states to separate; the evoked time course earns +0.040 with every
subject positive. **The `thingseeg2 --space evoked` captures therefore publish a
`cross_user_margin`, and the band-power captures still publish none** — the same
rule applied to a different answer.

**Two things about that second row that a hostile reader will find first, so
they are here.**

*It is barely a feature space.* `evoked800d4` computes nothing — it drops the
first 200 ms of the window and keeps every fourth sample. At a 1 Hz stride that
is close to shipping T2 at 25 Hz and calling it T1. The honest reading of the
result is therefore narrower than "the evoked space is better": it is *a T1 that
preserves time resolution beats a T1 that trades all of it for spectral
resolution, on a phase-locked visual response.* That is still worth knowing, and
it is still a legitimate T1 under R-5.4 — nothing in §5 requires a transform to
be lossy — but it is not a clever transform beating a naive one.

*The stimulus locking is the dataset's, not the device's.* Every window here is
exactly one epoch because the release is epoched, so the 800 ms tail is
guaranteed to be the post-stimulus interval. A device streaming continuously at
a 1 s stride would have arbitrary phase against any stimulus, and a
time-resolved space is exactly the kind that loses most from that. This margin
is measured under perfect stimulus alignment and should be read as an upper
bound for one. It is also why these captures do **not** declare
`akasara.align.v1`: R-8 wants stimulus lock within 10 ms as a property of the
*device*, and here it is a property of somebody's preprocessing.

Why the band-power space loses so much is worth stating precisely, because it is
not "band power is bad". The ASE path computes log power **per epoch** and the
consumer averages the resulting vectors; averaging in the feature domain keeps
induced power and discards phase locking, and the visual evoked response is
phase-locked. Doing it the other way round — average the epochs first, then take
band power, which is what an off-line analysis usually does — recovers part of
it (2.5x chance rather than 2.0x, margin +0.0029, CI [+0.0015, +0.0043]). The order
of averaging is not a detail here, and nothing in the descriptor records it,
because it happens in the consumer.

### The margin is earned on adapted data, so it was controlled for

THINGS-EEG2's samples are whitened per participant (R-5.5.1 above). Whitening
removes the common-mode covariance that a channel-mean baseline lives on, so it
could in principle manufacture an R-11.5 margin instead of revealing one. That
cannot be tested on this dataset — the un-whitened stream is not distributed —
so it was tested where both versions exist. Ninapro DB5, as released, and again
after the same kind of per-subject whitening fitted once and frozen:

| | full P@1 | channel-mean | margin | 95% CI |
| --- | --- | --- | --- | --- |
| as released | 0.224 | 0.062 | +0.162 | [+0.153, +0.172] |
| per-subject whitened | 0.166 | 0.050 | +0.116 | [+0.102, +0.130] |

Paired over subjects, whitening **costs** −0.046 of margin, CI [−0.055, −0.038],
0/6 subjects up. It suppresses the margin rather than inventing one, so the EEG
figure above is if anything understated by its own preprocessing. Different
signal and a full-covariance whitening rather than MVNN's noise-covariance one:
this bounds the direction, not the size.

### The layout the descriptor does not state

R-5.4 pins a feature space by id, and the order of `values[]` is part of what is
pinned — but no field states it. This producer is feature-major (every channel's
RMS, then every channel's WL); `apps/gate` writes the same two features
channel-major. Reducing one as if it were the other averages RMS together with
waveform length and reports the result as an R-11.5 baseline, which is wrong and
silent. `align.py` therefore keys the reduction off the feature-space id and
**refuses an id it has not been told about** rather than guessing; `--layout`
overrides. This is a gap in the spec as much as in the tool.

### Two estimator choices

Both deliberate, both from having got them wrong before:
the unit of replication is the **subject**, not the ordered pair (pairs share
subjects, so a pair-level interval is narrower than the evidence warrants), and
the comparison is **paired** — full and reduced are scored on the same split of
the same pair, and the interval is over the per-subject difference.

## Honest limits

- **The `quality` proxy is an upper bound.** Appendix A wants electrode-skin
  impedance; a recording has none and never will. The proxy captures railing and
  power-line contamination — the two failure modes visible in the samples — and
  misses contact impedance entirely. A badly-contacted but well-shielded
  electrode scores high here and would score low on a device. Read these values
  as "not visibly broken", not "verified good". Defined in `quality.py`.
- **One axial number is nominal, not measured.** DB5 records that the second
  armband sits "just below" the first and nothing more, so `axial_mm` uses the
  nominal armband width and the montage says so in
  `akasara.axial_mm_basis`. R-4.2.3 exists precisely so a consumer can see that
  a placement claim is nominal. Everything else in the montage — 8 electrodes
  45° apart per band, the second band offset 22.5°, the side, and the per-subject
  forearm circumference that makes electrode *spacing* comparable — is from the
  acquisition protocol and the recording itself.
- **`akasara.align.v1` is not declared, deliberately.** DB5 has cue labels, so
  the profile looks applicable, but R-8 requires stimulus-lock within 10 ms and
  DB5's `restimulus` is a post-hoc algorithmic relabelling whose error against
  true movement onset is not published. Declaring the profile would be claiming
  a timing accuracy nobody measured. The cues ship as a vendor extension
  (`akasara.cue`) instead, which claims nothing.
- **The self-test shares a code path with the frames.** For a software-only
  producer it cannot not — there is no firmware to be independently wrong. The
  genuinely independent check is against `conformance/selftest.mjs`: the input
  generator was re-implemented from the §5.7 formula and agrees with the
  reference to under 1e-12, which is a check on the *prose*, not on a shared
  library.
- **The EEG full scale is a stated constant, not a physical unit.** ds007822's
  BIDS sidecar declares microvolts; the recorded values run six orders of
  magnitude above anything physiological, so the published unit is not usable.
  One fixed constant in dataset-native units is applied to every subject
  identically, and the descriptor says so. Deriving the scale per recording
  would have been more flattering and would have made the transform per-user
  **adaptive**, which R-5.5 requires a device to declare and offer a way out of.
  A constant is the only version of this that is not quietly adaptive.
- **A cue-labelled window is only 35–39% of a DB5 capture.** The rest is rest and
  transitions. A window straddling a cue boundary is left unlabelled rather than
  assigned to whichever cue covers more of it.
- **On THINGS-EEG2 the `quality` proxy is empty, and says nothing false.** The
  release is 100 Hz, so the 50 Hz mains sits exactly at Nyquist: it has aliased
  somewhere unknowable and `quality.py` refuses to report a line share rather
  than inventing one. Whitened samples do not rail either. Every channel
  therefore reports 1.0, which is honest — "nothing visible is broken" — and
  carries no information. Appendix A's proxy has nothing to work with on a
  stream that arrives already preprocessed and downsampled; a device would
  measure impedance and would not be in this position.
- **The THINGS-EEG2 epoch order is the distribution's, not the recording's.**
  The preprocessed release is indexed `[condition][repetition]` and does not
  carry acquisition order, so the replayed stream is laid out condition-major.
  No reordering could restore the real order and none is attempted. The analysis
  window is exactly one epoch and the stride equals it, so no frame is ever an
  average of two different moments.
- **Its `don_count` is 1, and the original study had four sessions.** The
  release does not say which epoch came from which session, so 1 is the only
  number the file supports. It understates the donning variation in the data.

## ABF — §9.2 in a second language

`abf.py` implements the binary frame from the layout table, because §9.2 is the
part a vendor writes in firmware against nothing but that table. Encoding here
and decoding in `conformance/abf.mjs`, and the reverse, agree byte-for-byte
across all three value encodings — which is a check on the table, not on a
shared library. f32 round-trips exactly; f16 and int16+scale stay inside 1e-3 on
the reference frame, which is the territory R-9.1 governs.

## Tests

```
python test_replay.py --root <ninapro_db5 dir> --eeg-root <ds007822 dir> \
                      --te2-root <things-eeg2 dir>
```

46 tests with all three roots, 36 without — the dataset suites skip when their
root is absent, and everything else runs anywhere.
Included: the multi-session regression in both directions, the R-9.2 rounding
rule pinned across both codecs, cross-language self-test agreement to under
1e-12, an end-to-end WebSocket client with the §10.4 control plane, a check that
the transform carries no state between windows, and a check that `bandpower`
refuses a window too short to resolve the band it claims rather than returning a
number anyway.

## Next

- **A third producer nobody here wrote.** Two implementations by the same author
  is better than one, and is still not a vendor. The open question ASE cannot
  answer about itself is whether a firmware team reads §4 and §5 the same way.
  `apps/brainflow` narrows this — it is a third implementation against somebody
  else's acquisition API, on hardware the author does not own — but it is still
  the same author, so the question stands.
- ~~**T0 and T2/T3 paths**~~ **Done, 2026-07-30.** T0 in `apps/gate` (a hysteresis
  recogniser over the exported vectors, so R-3.2.2's citation is real), T2/T3 here.
  Implementing T0 found the fifth defect: `type = 0x02` had a header slot and a
  BLE characteristic and **no payload definition anywhere** — R-5.4.1 one tier
  down. Now R-9.5, and the two codecs agree byte-for-byte on it.

## T2 / T3 — and the badge this producer refuses

```
python replay.py --root <db5> --subject s1 --out out/db5-s1        # writes raw/
python replay.py --root <db5> --subject s1 --out out/db5-s1 --no-raw-tiers
```

R-3.3.1 says a declared badge must state what the numbers *are*. That splits the
two datasets, and the split comes from the recordings rather than from the code:

| | `ase.t2` | `ase.t3` | why |
| --- | --- | --- | --- |
| **Ninapro DB5** | yes, `a.u.` | **yes**, `count`, 8-bit, 1 LSB/count | The Myo streams signed 8-bit and Thalmic published no microvolt calibration, so `count` is the only true answer — a plausible `uV` would have been an invention. |
| **ds007822 PD-EEG** | yes, `a.u.` | **no** | The BIDS sidecar says microvolts and the values run to ~1e9. There is no honest `unit` and no knowable `adc_bits`, so the badge is absent rather than filled in. |
| **THINGS-EEG2** | **no** | **no** | No T3 for the same reason as the row above, and no T2 either — which is the part worth noticing. T2 is the stream "after fixed, documented filtering", and the last stage that produced these samples is fitted per participant. A whitened stream is not this producer's T2, so it claims neither badge and exports `tiers: ["t1"]` alone. |

T2 is written as float32 `.npy` per session plus an index, not JSONL: §10's own
conclusion is that this tier belongs on a wide link and in a binary container.
The chain applied is read out of the descriptor, so a descriptor edit changes the
bytes — and a stage that cannot exist at the sample rate (a 450 Hz lowpass on a
200 Hz recording) is refused rather than silently clamped. T3 **undoes** the
normalisation `sources.py` applies for T1, because a T3 stream carrying
normalised floats is a T2 with the wrong label.

Run against both real datasets, and the table above is what came out rather than
what was declared. DB5 subject s1 writes `tiers t1, t2, t3`, 568,540 samples ×
16 channels; the T3 array lands at **min −128, max +127** — the signed 8-bit
`count` the descriptor claims, arrived at from the recording and not from the
sidecar — with the T2 array filtered and correlating 0.95 against it. ds007822
sub-G01S01 writes `tiers t1, t2` and **no T3**, so the refusal in the second row
is a property of the output and not only of the prose.
